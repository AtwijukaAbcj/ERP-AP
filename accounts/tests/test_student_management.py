import tempfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import (
    Permission,
    Role,
    RolePermission,
    Student,
    StudentDocument,
    StudentStatusHistory,
    UserPermission,
    User,
)
from accounts.forms import StudentAddForm
from core.models import Semester
from audit.models import ActivityLog
from course.models import Program
from accounts.student_services import transition_student_status


@override_settings(LANGUAGE_CODE="en")
class StudentManagementTests(TestCase):
    def setUp(self):
        self.document_storage = StudentDocument._meta.get_field("file").storage
        self.original_document_storage_location = self.document_storage.location
        self.temporary_document_storage = tempfile.TemporaryDirectory()
        self.document_storage._location = self.temporary_document_storage.name
        self.document_storage.__dict__.pop("location", None)
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.semester = Semester.objects.create(semester="First")
        self.registrar = User.objects.create_user(
            username="records-registrar",
            email="registrar@example.test",
            password="test-password",
            is_registrar=True,
        )
        self.student_user = User.objects.create_user(
            username="student-owner",
            email="student@example.test",
            password="test-password",
            first_name="Amina",
            last_name="Kato",
        )
        self.student = Student.objects.create(
            student=self.student_user,
            registration_number="BSN-2026-001",
            program=self.program,
            semester=self.semester,
            cohort="2026 August",
        )

    def tearDown(self):
        for document in StudentDocument.objects.all():
            if document.file:
                document.file.storage.delete(document.file.name)
        self.document_storage._location = self.original_document_storage_location
        self.document_storage.__dict__.pop("location", None)
        self.temporary_document_storage.cleanup()

    def test_student_status_transition_records_history_and_audit_event(self):
        transition_student_status(
            self.student.pk,
            Student.Status.ON_LEAVE,
            self.registrar,
            "Approved leave",
        )

        self.student.refresh_from_db()
        history = StudentStatusHistory.objects.get(student=self.student)
        self.assertEqual(self.student.status, Student.Status.ON_LEAVE)
        self.assertEqual(history.from_status, Student.Status.ACTIVE)
        self.assertEqual(history.to_status, Student.Status.ON_LEAVE)
        self.assertEqual(history.changed_by, self.registrar)
        self.assertEqual(ActivityLog.objects.filter(target_model="accounts.Student").count(), 1)

    def test_graduated_student_cannot_be_reactivated(self):
        self.student.status = Student.Status.GRADUATED
        self.student.save(update_fields=("status",))

        with self.assertRaises(ValidationError):
            transition_student_status(
                self.student.pk,
                Student.Status.ACTIVE,
                self.registrar,
            )

    def test_registrar_can_list_and_view_student_records(self):
        self.client.force_login(self.registrar)

        list_response = self.client.get(reverse("student_list"))
        detail_response = self.client.get(
            reverse("student_record_detail", kwargs={"pk": self.student.pk})
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, self.student.registration_number)

    def test_superuser_sees_one_student_records_link_active_on_list_and_detail(self):
        admin = User.objects.create_superuser(
            username="student-nav-admin",
            email="student-nav-admin@example.test",
            password="test-password",
        )
        self.client.force_login(admin)
        student_list_url = reverse("student_list")

        for url in (
            student_list_url,
            reverse("student_record_detail", kwargs={"pk": self.student.pk}),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                sidebar_menu = html.split(
                    '<nav class="sidebar-menu">',
                    maxsplit=1,
                )[1].split("</nav>", maxsplit=1)[0]
                link = f'href="{student_list_url}"'
                self.assertEqual(sidebar_menu.count(link), 1)
                self.assertIn(
                    f'{link} class="active"',
                    sidebar_menu,
                )
                self.assertContains(
                    response,
                    reverse(
                        "user_password_reset",
                        args=(self.student_user.pk,),
                    ),
                )

    def test_student_can_view_own_record_but_not_another_record(self):
        other_user = User.objects.create_user(
            username="other-student",
            email="other@example.test",
            password="test-password",
        )
        other_student = Student.objects.create(
            student=other_user,
            registration_number="BSN-2026-002",
            program=self.program,
        )
        self.client.force_login(self.student_user)

        own_response = self.client.get(
            reverse("student_record_detail", kwargs={"pk": self.student.pk})
        )
        other_response = self.client.get(
            reverse("student_record_detail", kwargs={"pk": other_student.pk})
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)

    def test_student_directory_is_scoped_to_the_signed_in_student(self):
        self.student_user.is_student = True
        self.student_user.save(update_fields=("is_student",))
        other_user = User.objects.create_user(
            username="private-other-student",
            email="private-other@example.test",
            password="student-test-password",
            is_student=True,
        )
        Student.objects.create(
            student=other_user,
            registration_number="BSN-2026-002",
            program=self.program,
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.registration_number)
        self.assertNotContains(response, "BSN-2026-002")
        self.assertNotContains(response, "private-other@example.test")
        self.assertContains(response, "My Student Record")
        self.assertNotContains(response, reverse("add_student"))

    def test_post_login_landing_routes_student_to_student_page(self):
        self.student_user.is_student = True
        self.student_user.save(update_fields=("is_student",))
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("account_landing"))

        self.assertRedirects(response, reverse("student_list"))

    def test_student_management_sidebar_exposes_permission_gated_actions(self):
        self.client.force_login(self.registrar)

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        sidebar_menu = html.split(
            '<nav class="sidebar-menu">',
            maxsplit=1,
        )[1].split("</nav>", maxsplit=1)[0]
        self.assertIn(reverse("student_list"), sidebar_menu)
        self.assertIn(reverse("add_student"), sidebar_menu)
        self.assertNotIn(reverse("student_list_pdf"), sidebar_menu)
        self.assertContains(response, "student-directory-table")
        self.assertContains(response, "student-actions")
        self.assertContains(response, 'aria-label="Edit student"')
        self.assertContains(response, 'aria-label="Withdraw student"')

    def test_student_record_permission_grants_list_access(self):
        user = User.objects.create_user(
            username="student-records-officer",
            email="officer@example.test",
            password="test-password",
        )
        role = Role.objects.create(name="Student Records Officer", slug="student-records-officer")
        permission = Permission.objects.get(
            module="students",
            action="view_students",
        )
        RolePermission.objects.create(role=role, permission=permission)
        user.role = role
        user.save(update_fields=("role",))
        self.client.force_login(user)

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 200)

    def test_student_registration_number_is_generated_automatically(self):
        form = StudentAddForm(
            data={
                "first_name": "Musa",
                "last_name": "Okello",
                "email": "musa@example.test",
                "gender": "M",
                "address": "Kampala",
                "phone": "0700000000",
                "level": StudentAddForm.base_fields["level"].choices[0][0],
                "year": StudentAddForm.base_fields["year"].choices[0][0],
                "program": self.program.pk,
                "semester": self.semester.pk,
                "cohort": "August 2026",
            }
        )

        self.assertNotIn("registration_number", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        created_student = Student.objects.get(student=user)
        self.assertRegex(
            created_student.registration_number,
            r"^PN-Aug-26-\d{6}$",
        )

    def test_explicit_permission_deny_overrides_registrar_access(self):
        permission = Permission.objects.get(
            module="students",
            action="manage_students",
        )
        UserPermission.objects.create(
            user=self.registrar,
            permission=permission,
            effect=UserPermission.DENY,
        )
        self.client.force_login(self.registrar)

        response = self.client.get(reverse("add_student"))

        self.assertEqual(response.status_code, 403)

    def test_withdraw_action_archives_without_deleting_student_or_user(self):
        self.client.force_login(self.registrar)

        response = self.client.post(
            reverse("student_delete", kwargs={"pk": self.student.pk}),
            {"reason": "Transferred to another school"},
        )

        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.assertEqual(self.student.status, Student.Status.WITHDRAWN)
        self.assertTrue(User.objects.filter(pk=self.student_user.pk).exists())
        self.assertEqual(StudentStatusHistory.objects.filter(student=self.student).count(), 1)

    def test_student_document_is_private_and_requires_owner_or_document_permission(self):
        self.client.force_login(self.registrar)
        response = self.client.post(
            reverse("student_document_upload", kwargs={"pk": self.student.pk}),
            {
                "category": StudentDocument.Category.ACADEMIC,
                "title": "Transcript",
                "file": SimpleUploadedFile(
                    "transcript.pdf",
                    b"%PDF-1.4 student transcript",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        document = StudentDocument.objects.get(student=self.student)
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertNotEqual(
            document.file.storage.location,
            settings.MEDIA_ROOT,
        )
        with self.assertRaises(ValueError):
            document.file.url

        self.client.force_login(self.student_user)
        owner_download = self.client.get(
            reverse(
                "student_document_download",
                kwargs={
                    "student_pk": self.student.pk,
                    "document_pk": document.pk,
                },
            )
        )
        self.assertEqual(owner_download.status_code, 200)
        self.assertEqual(owner_download["Content-Disposition"].split(";")[0], "attachment")
        owner_download.close()

        unauthorized = User.objects.create_user(
            username="unrelated-user",
            email="unrelated@example.test",
            password="test-password",
        )
        self.client.force_login(unauthorized)
        denied_download = self.client.get(
            reverse(
                "student_document_download",
                kwargs={
                    "student_pk": self.student.pk,
                    "document_pk": document.pk,
                },
            )
        )
        self.assertEqual(denied_download.status_code, 403)

from django import forms
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from accounts.models import Permission, Role, RolePermission, Student, User
from course.models import Program
from core.models import Semester, Session
from .forms import AdmissionApplicationForm
from .models import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
)
from .services import transition_application


@override_settings(LANGUAGE_CODE="en")
class AdmissionsWorkflowTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.semester = Semester.objects.create(semester="First")
        self.registrar = User.objects.create_user(
            username="registrar",
            email="registrar@example.test",
            password="test-password",
            is_registrar=True,
        )
        self.application = Application.objects.create(
            first_name="Amina",
            last_name="Kato",
            email="amina@example.test",
            phone="0700000000",
            program=self.program,
            intake="August",
            academic_year="2026/2027",
        )

    def test_application_number_is_generated_and_status_history_is_recorded(self):
        self.assertRegex(self.application.application_number, r"^APP-\d{4}-\d{6}$")

        transition_application(
            self.application.pk,
            Application.Status.SCREENING,
            self.registrar,
            "Documents checked",
        )

        self.application.refresh_from_db()
        history = ApplicationStatusHistory.objects.get(application=self.application)
        self.assertEqual(self.application.status, Application.Status.SCREENING)
        self.assertEqual(history.from_status, Application.Status.SUBMITTED)
        self.assertEqual(history.to_status, Application.Status.SCREENING)
        self.assertEqual(history.changed_by, self.registrar)
        self.assertEqual(history.comment, "Documents checked")

    def test_application_intake_and_academic_year_are_select_fields(self):
        Session.objects.create(session="2032/2033")
        form = AdmissionApplicationForm()

        self.assertIsInstance(form.fields["intake"], forms.ChoiceField)
        self.assertIsInstance(
            form.fields["academic_year"],
            forms.ChoiceField,
        )
        self.assertIn(("August", "August Intake"), form.fields["intake"].choices)
        self.assertIn(("2032/2033", "2032/2033"), form.fields["academic_year"].choices)

    def test_application_form_keeps_existing_intake_and_rejects_unknown_choices(self):
        Application.objects.create(
            first_name="Legacy",
            last_name="Applicant",
            email="legacy@example.test",
            phone="0700000002",
            intake="DEMO Intake",
            academic_year="2026/2027",
        )
        form = AdmissionApplicationForm(
            data={
                "first_name": "New",
                "last_name": "Applicant",
                "email": "new@example.test",
                "phone": "0700000003",
                "program": self.program.pk,
                "intake": "DEMO Intake",
                "academic_year": "2026/2027",
            }
        )

        self.assertIn(
            ("DEMO Intake", "DEMO Intake"),
            form.fields["intake"].choices,
        )
        self.assertTrue(form.is_valid(), form.errors)
        invalid_form = AdmissionApplicationForm(
            data={
                "first_name": "New",
                "last_name": "Applicant",
                "email": "other@example.test",
                "phone": "0700000004",
                "program": self.program.pk,
                "intake": "Unlisted Intake",
                "academic_year": "not-a-year",
            }
        )
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("intake", invalid_form.errors)
        self.assertIn("academic_year", invalid_form.errors)

    def test_application_can_move_to_any_active_status(self):
        self.application.status = Application.Status.REJECTED
        self.application.save(update_fields=("status",))

        transition_application(
            self.application.pk,
            Application.Status.ACCEPTED,
            self.registrar,
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.ACCEPTED)

    def test_create_application_requires_admissions_permission(self):
        user = User.objects.create_user(
            username="ordinary",
            email="ordinary@example.test",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admissions:application_create"))

        self.assertEqual(response.status_code, 403)

    def test_registrar_can_create_and_view_applications(self):
        self.client.force_login(self.registrar)
        form_response = self.client.get(reverse("admissions:application_create"))
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, "admission-application-form")
        self.assertContains(form_response, "form-select")
        self.assertContains(form_response, "col-md-6 col-lg-4")

        create_response = self.client.post(
            reverse("admissions:application_create"),
            {
                "first_name": "Musa",
                "last_name": "Okello",
                "email": "musa@example.test",
                "phone": "0711111111",
                "program": self.program.pk,
                "intake": "January",
                "academic_year": "2026/2027",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        created_application = Application.objects.get(email="musa@example.test")
        self.assertEqual(created_application.created_by, self.registrar)
        detail_response = self.client.get(
            reverse(
                "admissions:application_detail",
                kwargs={"pk": created_application.pk},
            )
        )
        self.assertEqual(detail_response.status_code, 200)

    def test_role_permission_grants_admissions_view(self):
        user = User.objects.create_user(
            username="admissions-officer",
            email="officer@example.test",
            password="test-password",
        )
        role = Role.objects.create(name="Admissions Officer", slug="admissions-officer")
        permission = Permission.objects.get(
            module="admissions",
            action="view_applications",
        )
        RolePermission.objects.create(role=role, permission=permission)
        user.role = role
        user.save(update_fields=("role",))
        self.client.force_login(user)

        response = self.client.get(reverse("admissions:application_list"))

        self.assertEqual(response.status_code, 200)

    def test_registrar_can_create_application_status(self):
        self.client.force_login(self.registrar)
        response = self.client.post(
            reverse("admissions:application_status_settings"),
            {"name": "Awaiting deposit"},
        )

        self.assertRedirects(
            response,
            reverse("admissions:application_status_settings"),
        )
        custom_status = ApplicationStatus.objects.get(code="awaiting-deposit")
        self.assertTrue(custom_status.is_active)

    def test_all_active_statuses_are_available_and_current_is_selected(self):
        self.client.force_login(self.registrar)
        custom_status = ApplicationStatus.objects.create(
            code="awaiting-deposit",
            name="Awaiting deposit",
        )

        self.application.status = Application.Status.ACCEPTED
        self.application.save(update_fields=("status",))
        detail = self.client.get(
            reverse(
                "admissions:application_detail",
                kwargs={"pk": self.application.pk},
            )
        )
        self.assertContains(detail, "Awaiting deposit")
        self.assertContains(
            detail,
            f'<option value="{Application.Status.ACCEPTED}" selected>',
            html=False,
        )
        self.assertContains(detail, f'<option value="{custom_status.code}">')
        change_response = self.client.post(
            reverse(
                "admissions:application_change_status",
                kwargs={"pk": self.application.pk},
            ),
            {"status": custom_status.code, "comment": "Deposit pending"},
        )

        self.assertRedirects(
            change_response,
            reverse(
                "admissions:application_detail",
                kwargs={"pk": self.application.pk},
            ),
        )
        self.application.refresh_from_db()
        history = ApplicationStatusHistory.objects.get(application=self.application)
        self.assertEqual(self.application.get_status_display(), "Awaiting deposit")
        self.assertEqual(history.get_to_status_display(), "Awaiting deposit")

    def test_deactivated_status_is_removed_from_status_dropdown(self):
        self.client.force_login(self.registrar)
        custom_status = ApplicationStatus.objects.create(
            code="awaiting-deposit",
            name="Awaiting deposit",
        )
        self.application.status = Application.Status.ACCEPTED
        self.application.save(update_fields=("status",))

        response = self.client.post(
            reverse(
                "admissions:application_status_toggle",
                kwargs={"pk": custom_status.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("admissions:application_status_settings"),
        )
        custom_status.refresh_from_db()
        self.assertFalse(custom_status.is_active)
        detail = self.client.get(
            reverse(
                "admissions:application_detail",
                kwargs={"pk": self.application.pk},
            )
        )
        self.assertNotContains(detail, 'value="awaiting-deposit"')

    def test_accepted_application_can_link_matching_student_record(self):
        self.application.status = Application.Status.ACCEPTED
        self.application.save(update_fields=("status",))
        student_user = User.objects.create_user(
            username="student-user",
            email="student@example.test",
            password="test-password",
            first_name="Amina",
            last_name="Kato",
        )
        student = Student.objects.create(
            student=student_user,
            program=self.program,
            registration_number="BSN-2026-001",
        )
        self.client.force_login(self.registrar)

        response = self.client.post(
            reverse(
                "admissions:application_link_student",
                kwargs={"pk": self.application.pk},
            ),
            {"student": student.pk},
        )

        self.assertEqual(response.status_code, 302, response.content.decode())
        self.application.refresh_from_db()
        self.assertEqual(self.application.linked_student, student)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_accepted_application_can_create_student_and_send_password_setup(self):
        self.application.status = Application.Status.ACCEPTED
        self.application.save(update_fields=("status",))
        self.client.force_login(self.registrar)

        response = self.client.post(
            reverse(
                "admissions:application_provision_student",
                kwargs={"pk": self.application.pk},
            ),
            {
                "level": "Bachelor",
                "year": 1,
                "semester": self.semester.pk,
            },
        )

        self.assertEqual(response.status_code, 302, response.content.decode())
        self.application.refresh_from_db()
        student = self.application.linked_student
        self.assertRegex(
            student.registration_number,
            r"^PN-Aug-26-\d{6}$",
        )
        self.assertEqual(student.program, self.program)
        self.assertEqual(student.level, "Bachelor")
        self.assertEqual(student.year, 1)
        self.assertEqual(student.semester, self.semester)
        self.assertEqual(student.student.email, self.application.email)
        self.assertTrue(student.student.is_student)
        self.assertTrue(student.student.has_usable_password())
        setup_emails = [
            email
            for email in mail.outbox
            if self.application.email in email.to
            and "password" in email.subject.lower()
        ]
        self.assertEqual(len(setup_emails), 1)
        self.assertIn("password", setup_emails[0].subject.lower())

    def test_accepted_application_does_not_claim_an_existing_user_email(self):
        self.application.status = Application.Status.ACCEPTED
        self.application.save(update_fields=("status",))
        User.objects.create_user(
            username="existing-applicant-account",
            email=self.application.email,
            password="test-password",
        )
        self.client.force_login(self.registrar)

        response = self.client.post(
            reverse(
                "admissions:application_provision_student",
                kwargs={"pk": self.application.pk},
            ),
            {
                "level": "Bachelor",
                "year": 1,
                "semester": self.semester.pk,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "An account already uses this email", status_code=400)
        self.application.refresh_from_db()
        self.assertIsNone(self.application.linked_student)

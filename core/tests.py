from io import StringIO

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from accounts.models import (
    Permission,
    Role,
    RolePermission,
    Student,
    User,
    UserPermission,
)
from django.core.mail import EmailMessage
from admissions.models import Application, ApplicationStatus
from audit.models import ActivityLog as AuditActivityLog
from clinical.models import ClinicalLogEntry, ClinicalPlacement, Ward
from course.models import (
    Course,
    CourseAllocation,
    Program,
    Upload,
    UploadVideo,
)
from finance.models import FeeCategory, Invoice, InvoicePayment, Staff
from procurement.models import (
    ProcurementStatus,
    PurchaseOrder,
    PurchaseQuotation,
    PurchaseRequisition,
    Supplier,
)
from result.models import (
    AttendanceRecord,
    CourseAssignment,
    Result,
    TakenCourse,
)

from .email_backend import DatabaseConfiguredEmailBackend
from .models import (
    EmailServerSettings,
    NewsAndEvents,
    Room,
    Semester,
    Session,
    SiteSettings,
    Timetable,
    TimetableEntry,
)


@override_settings(LANGUAGE_CODE="en")
class EmailServerSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="email-settings-admin",
            email="email-settings-admin@example.test",
            password="test-password",
        )
        self.client.force_login(self.admin)

    def test_dashboard_can_save_smtp_settings_and_keeps_password_encrypted(self):
        response = self.client.get(reverse("site_settings_email"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email Server (SMTP)")
        self.assertContains(response, 'name="host"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="from_email"')

        response = self.client.post(
            reverse("site_settings_email"),
            {
                "host": "smtp.example.test",
                "port": "465",
                "username": "mailer@example.test",
                "password": "Replacement-Only-Test-Password",
                "use_tls": "",
                "use_ssl": "on",
                "from_email": "noreply@example.test",
                "from_name": "FalconLMS",
                "is_enabled": "on",
            },
        )

        self.assertRedirects(response, reverse("site_settings_email"))
        email_settings = EmailServerSettings.objects.get(pk=1)
        self.assertEqual(email_settings.host, "smtp.example.test")
        self.assertEqual(email_settings.port, 465)
        self.assertFalse(email_settings.use_tls)
        self.assertTrue(email_settings.use_ssl)
        self.assertTrue(email_settings.is_enabled)
        self.assertNotEqual(
            email_settings.encrypted_password,
            "Replacement-Only-Test-Password",
        )
        self.assertEqual(
            email_settings.get_password(),
            "Replacement-Only-Test-Password",
        )

        response = self.client.get(reverse("site_settings_email"))
        self.assertNotContains(response, "Replacement-Only-Test-Password")
        self.assertContains(response, "password is configured")

    def test_settings_home_links_to_individual_settings_pages(self):
        response = self.client.get(reverse("site_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("site_settings_email"))
        self.assertContains(response, reverse("site_settings_branding"))
        self.assertContains(response, reverse("site_settings_school"))

    def test_branding_page_updates_only_branding_fields(self):
        response = self.client.get(reverse("site_settings_branding"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="site_name"')
        self.assertNotContains(response, 'name="school_name"')

        response = self.client.post(
            reverse("site_settings_branding"),
            {
                "site_name": "Updated Falcon",
                "site_tagline": "A learning platform",
                "primary_color": "#123456",
            },
        )

        self.assertRedirects(response, reverse("site_settings_branding"))
        settings = SiteSettings.get_settings()
        self.assertEqual(settings.site_name, "Updated Falcon")
        self.assertEqual(settings.primary_color, "#123456")

    def test_school_page_updates_only_school_information(self):
        response = self.client.get(reverse("site_settings_school"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="school_name"')
        self.assertNotContains(response, 'name="site_name"')

        response = self.client.post(
            reverse("site_settings_school"),
            {
                "school_name": "Updated School",
                "school_email": "office@example.test",
                "school_phone": "+1 555 0100",
                "school_address": "100 Main Street",
                "school_website": "https://school.example.test",
            },
        )

        self.assertRedirects(response, reverse("site_settings_school"))
        settings = SiteSettings.get_settings()
        self.assertEqual(settings.school_name, "Updated School")
        self.assertEqual(settings.school_email, "office@example.test")
        self.assertEqual(settings.site_name, "FalconLMS")

    def test_blank_password_keeps_existing_smtp_password(self):
        email_settings = EmailServerSettings.get_settings()
        email_settings.set_password("Existing-Test-Password")
        email_settings.save()

        response = self.client.post(
            reverse("site_settings_email"),
            {
                "host": "smtp.example.test",
                "port": "587",
                "username": "mailer@example.test",
                "password": "",
                "use_tls": "on",
                "use_ssl": "",
                "from_email": "noreply@example.test",
                "from_name": "",
                "is_enabled": "on",
            },
        )

        self.assertRedirects(response, reverse("site_settings_email"))
        email_settings.refresh_from_db()
        self.assertEqual(email_settings.get_password(), "Existing-Test-Password")

    def test_tls_and_ssl_cannot_both_be_selected(self):
        response = self.client.post(
            reverse("site_settings_email"),
            {
                "host": "smtp.example.test",
                "port": "465",
                "username": "mailer@example.test",
                "password": "",
                "use_tls": "on",
                "use_ssl": "on",
                "from_email": "noreply@example.test",
                "from_name": "",
                "is_enabled": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["email_form"].non_field_errors())

    def test_dashboard_email_settings_require_a_host_when_enabled(self):
        response = self.client.post(
            reverse("site_settings_email"),
            {
                "host": "",
                "port": "587",
                "username": "",
                "password": "",
                "use_tls": "on",
                "use_ssl": "",
                "from_email": "",
                "from_name": "",
                "is_enabled": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("host", response.context["email_form"].errors)

    @override_settings(
        EMAIL_ENV_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )
    def test_disabled_dashboard_settings_preserve_environment_backend(self):
        EmailServerSettings.objects.create(
            host="smtp.example.test",
            port=587,
            is_enabled=False,
        )
        backend = DatabaseConfiguredEmailBackend()
        message = EmailMessage(
            "Test",
            "Test body",
            "env-sender@example.test",
            ["recipient@example.test"],
        )

        self.assertEqual(backend.send_messages([message]), 1)
        self.assertEqual(message.from_email, "env-sender@example.test")

    @patch("core.email_backend.SMTPEmailBackend")
    def test_database_backend_uses_saved_credentials_and_sender(self, smtp_backend):
        smtp_backend.return_value.send_messages.return_value = 1
        email_settings = EmailServerSettings.objects.create(
            host="smtp.example.test",
            port=465,
            username="mailer@example.test",
            use_tls=False,
            use_ssl=True,
            from_email="noreply@example.test",
            from_name="FalconLMS",
            is_enabled=True,
        )
        email_settings.set_password("SMTP-Test-Password")
        email_settings.save()
        message = EmailMessage(
            "Test",
            "Test body",
            "old-sender@example.test",
            ["recipient@example.test"],
        )

        backend = DatabaseConfiguredEmailBackend(
            username=None,
            password=None,
            fail_silently=False,
        )
        sent = backend.send_messages([message])

        self.assertEqual(sent, 1)
        self.assertEqual(
            message.from_email,
            "FalconLMS <noreply@example.test>",
        )
        smtp_backend.assert_called_once()
        self.assertEqual(
            smtp_backend.call_args.kwargs["password"],
            "SMTP-Test-Password",
        )


@override_settings(LANGUAGE_CODE="en")
class SemesterCurrentStateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="semester-admin",
            email="semester-admin@example.test",
            password="semester-test-password",
        )
        self.old_session = Session.objects.create(
            session="2025/2026",
            is_current_session=True,
        )
        self.target_session = Session.objects.create(session="2026/2027")
        self.semester = Semester.objects.create(
            semester="First",
            session=self.old_session,
            is_current_semester=True,
        )
        self.client.force_login(self.admin)

    def test_setting_active_semester_sets_its_session_as_current(self):
        response = self.client.post(
            reverse("edit_semester", args=(self.semester.pk,)),
            {
                "semester": "Second",
                "is_current_semester": "True",
                "session": self.target_session.pk,
                "next_semester_begins": "2026-12-01",
            },
        )

        self.assertRedirects(response, reverse("semester_list"))
        self.old_session.refresh_from_db()
        self.target_session.refresh_from_db()
        self.semester.refresh_from_db()
        self.assertFalse(self.old_session.is_current_session)
        self.assertTrue(self.target_session.is_current_session)
        self.assertTrue(self.semester.is_current_semester)
        self.assertEqual(self.semester.session, self.target_session)

    def test_unsetting_active_semester_does_not_clear_current_session(self):
        response = self.client.post(
            reverse("edit_semester", args=(self.semester.pk,)),
            {
                "semester": "First",
                "is_current_semester": "False",
                "session": self.old_session.pk,
                "next_semester_begins": "2026-12-01",
            },
        )

        self.assertRedirects(response, reverse("semester_list"))
        self.old_session.refresh_from_db()
        self.semester.refresh_from_db()
        self.assertTrue(self.old_session.is_current_session)
        self.assertFalse(self.semester.is_current_semester)


@override_settings(LANGUAGE_CODE="en")
class CourseEnrollmentManagementTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.semester = Semester.objects.create(
            semester="First",
            is_current_semester=True,
        )
        self.admin = User.objects.create_superuser(
            username="academic-admin",
            email="admin@example.test",
            password="test-password",
        )
        self.student_user = User.objects.create_user(
            username="academic-student",
            password="test-password",
            is_student=True,
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
            registration_number="BSN-2026-001",
        )
        self.course = Course.objects.create(
            title="Foundations of Mental Health",
            code="PMN101",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
        )
        self.client.force_login(self.admin)
        self.url = reverse("course_enrollment")

    def test_superuser_can_open_enrollment_management(self):
        response = self.client.get(self.url, {"course": self.course.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.registration_number)

    def test_admin_enrollment_and_removal_preserve_the_enrollment_record(self):
        self.client.post(
            self.url,
            {
                "action": "enroll",
                "course_id": self.course.pk,
                "student_ids": [self.student.pk],
            },
        )
        enrollment = TakenCourse.objects.get(student=self.student, course=self.course)
        self.assertEqual(enrollment.semester, self.semester)

        response = self.client.post(
            self.url,
            {
                "action": "unenroll",
                "course_id": self.course.pk,
                "enrollment_ids": [enrollment.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.is_dropped)
        self.assertEqual(enrollment.dropped_by, self.admin)
        self.assertIsNotNone(enrollment.dropped_at)
        self.assertTrue(TakenCourse.all_objects.filter(pk=enrollment.pk).exists())

    def test_non_admin_cannot_open_enrollment_management(self):
        self.client.force_login(self.student_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)


@override_settings(LANGUAGE_CODE="en")
class StudentTimetableTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.student_user = User.objects.create_user(
            username="timetable-student",
            password="test-password",
            is_student=True,
        )
        Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        self.course = Course.objects.create(
            title="Foundations of Mental Health",
            code="PMN101",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
        )
        self.lecturer = User.objects.create_user(
            username="timetable-lecturer",
            password="test-password",
            is_lecturer=True,
        )
        self.room = Room.objects.create(name="Lecture Room 1", capacity=40)
        self.timetable = Timetable.objects.create(
            program=self.program,
            semester="First",
            academic_year=self.session.session,
        )
        self.entry = TimetableEntry.objects.create(
            timetable=self.timetable,
            course=self.course,
            lecturer=self.lecturer,
            day="Monday",
            start_time="09:00",
            end_time="10:00",
            room=self.room,
        )

    def test_student_timetable_uses_current_academic_session(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("student_timetable"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertEqual(
            str(self.entry),
            "Foundations of Mental Health on Monday (09:00-10:00)",
        )


@override_settings(LANGUAGE_CODE="en")
class SchoolCalendarTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="calendar-admin",
            email="calendar-admin@example.test",
            password="test-password",
        )
        self.student = User.objects.create_user(
            username="calendar-student",
            password="test-password",
            is_student=True,
        )
        self.session = Session.objects.create(session="2026/2027")
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            registration_open_date=date(2026, 8, 1),
            registration_close_date=date(2026, 9, 1),
            add_drop_open_date=date(2026, 9, 2),
            add_drop_close_date=date(2026, 9, 10),
        )
        NewsAndEvents.objects.create(
            title="Clinical orientation",
            summary="Orientation for new clinical placements",
            posted_as="Event",
            event_date=date(2099, 10, 25),
            semester=self.semester,
        )

    def test_home_displays_upcoming_events_and_academic_calendar(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School Calendar")
        self.assertContains(response, "Clinical orientation")
        self.assertContains(response, "2026/2027")
        self.assertEqual(response.context["school_calendar"].count(), 1)

    def test_only_superusers_can_manage_calendar_news_and_events(self):
        self.client.force_login(self.student)

        self.assertEqual(self.client.get(reverse("add_item")).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("add_item")).status_code, 200)


@override_settings(LANGUAGE_CODE="en")
class InstitutionalReportingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="report-admin",
            email="report-admin@example.test",
            password="test-password",
        )
        self.session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.student_user = User.objects.create_user(
            username="report-student",
            password="test-password",
            is_student=True,
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
            registration_number="REPORT-001",
        )
        self.course = Course.objects.create(
            title="Mental Health Nursing",
            code="MHN101",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
        )

    def test_reports_aggregate_connected_school_modules_and_export_csv(self):
        TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.semester,
            assignment=Decimal("20.00"),
            mid_exam=Decimal("20.00"),
            quiz=Decimal("20.00"),
            attendance=Decimal("20.00"),
            final_exam=Decimal("20.00"),
        )
        AttendanceRecord.objects.create(
            student=self.student,
            course=self.course,
            date=date(2026, 10, 18),
            status="present",
            recorded_by=self.admin,
        )
        lecturer = User.objects.create_user(
            username="report-lecturer",
            email="report-lecturer@example.test",
            password="test-password",
            is_lecturer=True,
            is_staff=True,
        )
        Staff.objects.create(user=lecturer, qualification="Bachelor of Nursing")
        Upload.objects.create(
            title="Course handbook",
            course=self.course,
            file="course_files/handbook.pdf",
        )
        UploadVideo.objects.create(
            title="Introduction",
            course=self.course,
            video="course_videos/introduction.mp4",
        )
        CourseAssignment.objects.create(
            title="Reflective practice",
            course=self.course,
            max_score=Decimal("20.00"),
        )
        Application.objects.create(
            first_name="Admission",
            last_name="Applicant",
            email="applicant@example.test",
            phone="0700000000",
            intake="August",
            academic_year="2026/2027",
            program=self.program,
            status=Application.Status.ACCEPTED,
        )
        Invoice.objects.create(
            student=self.student,
            semester=self.semester,
            due_date=date(2026, 12, 1),
            total_amount=Decimal("1000.00"),
            paid_amount=Decimal("250.00"),
        )
        ward = Ward.objects.create(
            name="Acute Ward",
            capacity=5,
        )
        ClinicalPlacement.objects.create(
            student=self.student,
            ward=ward,
            semester=self.semester,
            supervisor=self.admin,
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 12, 1),
            status=ClinicalPlacement.Status.IN_PROGRESS,
        )
        supplier = Supplier.objects.create(name="Reporting Supplier")
        PurchaseOrder.objects.create(
            supplier=supplier,
            total_amount=Decimal("300.00"),
            approved=True,
        )
        pending_status = ProcurementStatus.objects.get_or_create(
            slug="pending_approval",
            defaults={"name": "Pending Approval"},
        )[0]
        PurchaseRequisition.objects.create(
            title="Pending equipment request",
            status=pending_status,
            total_amount=Decimal("200.00"),
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("institutional_reports"),
            {"semester": self.semester.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["student_count"], 1)
        self.assertEqual(response.context["active_enrollment_count"], 1)
        self.assertEqual(response.context["average_score"], Decimal("100"))
        self.assertEqual(response.context["pass_count"], 1)
        self.assertEqual(response.context["admission_total"], 1)
        self.assertEqual(response.context["clinical_placement_count"], 1)
        self.assertEqual(response.context["invoice_total"], Decimal("1000.00"))
        self.assertEqual(response.context["amount_paid"], Decimal("250.00"))
        self.assertEqual(response.context["outstanding"], Decimal("750.00"))
        self.assertEqual(response.context["approved_order_total"], Decimal("300.00"))
        self.assertEqual(response.context["open_requisition_count"], 1)
        self.assertEqual(response.context["attendance_total"], 1)
        self.assertEqual(response.context["attendance_rate"], Decimal("100.00"))
        self.assertEqual(response.context["students_by_level"][0]["count"], 1)
        self.assertEqual(
            response.context["lecturers_by_qualification"][0]["qualification"],
            "Bachelor of Nursing",
        )
        self.assertEqual(response.context["course_performance"][0]["enrollment_count"], 1)
        self.assertEqual(
            response.context["course_resource_counts"],
            {"courses": 1, "documents": 1, "videos": 1, "assignments": 1},
        )

        export_response = self.client.get(
            reverse("export_institutional_report_csv"),
            {"semester": self.semester.pk},
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertIn(b"Outstanding invoice balance,750", export_response.content)
        self.assertIn(b"Overall attendance rate (%),100.0", export_response.content)

        pdf_response = self.client.get(
            reverse("export_institutional_report_pdf"),
            {"semester": self.semester.pk},
        )
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

    def test_reporting_requires_role_permission_and_honors_explicit_denial(self):
        report_permission = Permission.objects.get(code="reports.view")
        reporting_role = Role.objects.create(
            name="Reporting Analyst",
            slug="reporting-analyst",
        )
        RolePermission.objects.create(
            role=reporting_role,
            permission=report_permission,
        )
        analyst = User.objects.create_user(
            username="report-analyst",
            password="test-password",
            role=reporting_role,
        )
        url = reverse("institutional_reports")

        self.client.force_login(analyst)
        self.assertEqual(self.client.get(url).status_code, 200)

        UserPermission.objects.create(
            user=analyst,
            permission=report_permission,
            effect=UserPermission.DENY,
        )
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_unprivileged_user_cannot_view_reports_or_csv_export(self):
        user = User.objects.create_user(
            username="no-report-access",
            password="test-password",
        )
        self.client.force_login(user)

        self.assertEqual(
            self.client.get(reverse("institutional_reports")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("export_institutional_report_csv")
            ).status_code,
            403,
        )


@override_settings(LANGUAGE_CODE="en")
class DashboardModuleNavigationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.test",
            password="dashboard-test-password",
        )
        self.client.force_login(self.admin)

    def test_dashboard_shows_all_ten_school_modules_with_working_destinations(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        modules = response.context["module_cards"]
        self.assertEqual(len(modules), 10)

        for module in modules:
            with self.subTest(module=module["title"]):
                self.assertContains(
                    response,
                    module["title"].replace("&", "&amp;"),
                )
                self.assertContains(response, f'href="{module["url"]}"')
                module_response = self.client.get(module["url"])
                self.assertEqual(module_response.status_code, 200)

    def test_dashboard_shows_analytics_graphs(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["course_count"], Course.objects.count())
        self.assertContains(response, "Traffic Analytics")
        self.assertContains(response, "Enrollment Trends")
        self.assertContains(response, "not page-view tracking")

    def test_dashboard_charts_use_real_lifecycle_counts(self):
        program = Program.objects.create(title="Dashboard Nursing")
        session = Session.objects.create(session="2026/2027")
        semester = Semester.objects.create(
            semester="First",
            session=session,
            is_current_semester=True,
        )
        student_user = User.objects.create_user(
            username="dashboard-chart-student",
            email="dashboard-chart-student@example.test",
            password="dashboard-test-password",
            is_student=True,
        )
        student = Student.objects.create(
            student=student_user,
            program=program,
            level="Bachelor",
            year=1,
            registration_number="DASH-001",
        )
        course = Course.objects.create(
            title="Dashboard Mental Health",
            code="DASH101",
            program=program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        TakenCourse.objects.create(
            student=student,
            course=course,
            semester=semester,
            assignment=Decimal("90.00"),
        )
        Application.objects.create(
            first_name="Dashboard",
            last_name="Applicant",
            email="dashboard-applicant@example.test",
            phone="0700000000",
            program=program,
            intake="August",
            academic_year=session.session,
            status=Application.Status.ACCEPTED,
        )
        custom_status = ApplicationStatus.objects.create(
            code="documents-pending",
            name="Documents Pending",
        )
        Application.objects.create(
            first_name="Custom",
            last_name="Status Applicant",
            email="custom-status@example.test",
            phone="0700000001",
            program=program,
            intake="August",
            academic_year=session.session,
            status=custom_status.code,
        )
        Invoice.objects.create(
            student=student,
            semester=semester,
            due_date=date(2026, 12, 1),
            total_amount=Decimal("100.00"),
            paid_amount=Decimal("40.00"),
        )
        ward = Ward.objects.create(name="Dashboard Ward", capacity=2)
        ClinicalPlacement.objects.create(
            student=student,
            ward=ward,
            semester=semester,
            supervisor=self.admin,
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 12, 1),
            status=ClinicalPlacement.Status.IN_PROGRESS,
        )
        AuditActivityLog.objects.create(
            user=self.admin,
            action="CREATE",
            description="Dashboard chart test activity",
        )
        AuditActivityLog.objects.create(
            user=student_user,
            action="VIEW",
            description="Dashboard student activity test",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        charts = response.context["dashboard_charts"]
        self.assertEqual(
            next(
                row["value"]
                for row in charts["admissions"]
                if row["label"] == "Accepted"
            ),
            1,
        )
        self.assertEqual(
            next(
                row["value"]
                for row in charts["admissions"]
                if row["label"] == "Documents Pending"
            ),
            1,
        )
        self.assertEqual(charts["enrollments"][0]["label"], program.title)
        self.assertEqual(charts["enrollments"][0]["value"], 1)
        traffic = response.context["traffic_trends"][-1]
        self.assertEqual(traffic["actions"], 2)
        self.assertEqual(traffic["users"], 2)
        traffic_types = {
            row["user_type"]: row
            for row in response.context["traffic_by_user_type"]
        }
        self.assertEqual(traffic_types["Admin"]["actions"], 1)
        self.assertEqual(traffic_types["Student"]["users"], 1)
        enrollment = response.context["enrollment_trends"][0]
        self.assertEqual(enrollment["label"], "2026/2027 · First")
        self.assertEqual(enrollment["value"], 1)
        self.assertEqual(enrollment["x"], 330)
        self.assertEqual(
            next(row["value"] for row in charts["results"] if row["label"] == "A+"),
            1,
        )
        self.assertEqual(
            next(
                row["value"]
                for row in charts["placements"]
                if row["label"] == "In progress"
            ),
            1,
        )
        self.assertEqual(charts["finance"][0]["value"], Decimal("40.00"))
        self.assertEqual(charts["finance"][1]["value"], Decimal("60.00"))
        self.assertContains(response, "Student lifecycle analytics")


@override_settings(
    LANGUAGE_CODE="en",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class StudentLifecycleIntegrationTests(TestCase):
    def setUp(self):
        self.registrar = User.objects.create_user(
            username="lifecycle-registrar",
            email="lifecycle-registrar@example.test",
            password="lifecycle-test-password",
            is_registrar=True,
        )
        clinical_permission, _ = Permission.objects.get_or_create(
            module="clinical",
            action="manage_placements",
            defaults={"name": "Manage clinical placements"},
        )
        UserPermission.objects.create(
            user=self.registrar,
            permission=clinical_permission,
            effect=UserPermission.GRANT,
            reason="Lifecycle integration test",
        )
        self.finance_manager = User.objects.create_user(
            username="lifecycle-finance",
            email="lifecycle-finance@example.test",
            password="lifecycle-test-password",
            is_finance_manager=True,
        )
        self.lecturer = User.objects.create_user(
            username="lifecycle-lecturer",
            email="lifecycle-lecturer@example.test",
            password="lifecycle-test-password",
            is_lecturer=True,
            first_name="Grace",
            last_name="Nurse",
        )
        self.student_user = User.objects.create_user(
            username="lifecycle-student",
            email="lifecycle-student@example.test",
            password="lifecycle-test-password",
            is_student=True,
            first_name="Amina",
            last_name="Kato",
        )
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
            registration_number="LIFE-2026-001",
        )
        self.session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.course = Course.objects.create(
            title="Foundations of Psychiatric Nursing",
            code="LIFE101",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        self.ward = Ward.objects.create(name="Lifecycle Ward", capacity=2)

    def test_student_moves_from_admission_through_billing_and_reporting(self):
        self.client.force_login(self.registrar)
        self.student.delete()
        create_application_response = self.client.post(
            reverse("admissions:application_create"),
            {
                "first_name": "Amina",
                "last_name": "Kato",
                "email": self.student_user.email,
                "phone": "0700000000",
                "program": self.program.pk,
                "intake": "August",
                "academic_year": self.session.session,
            },
        )
        self.assertEqual(create_application_response.status_code, 302)
        application = Application.objects.get(email=self.student_user.email)

        accept_response = self.client.post(
            reverse("admissions:application_change_status", args=(application.pk,)),
            {"status": Application.Status.ACCEPTED, "comment": "Requirements met."},
        )
        self.assertEqual(accept_response.status_code, 302)
        provision_response = self.client.post(
            reverse("admissions:application_provision_student", args=(application.pk,)),
            {
                "registration_number": "LIFE-2026-001",
                "level": "Bachelor",
                "year": 1,
            },
        )
        self.assertEqual(provision_response.status_code, 302)
        application.refresh_from_db()
        self.student = application.linked_student
        self.student_user = self.student.student
        self.assertEqual(application.linked_student, self.student)

        self.client.force_login(self.student_user)
        enrollment_response = self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )
        self.assertEqual(enrollment_response.status_code, 302)
        enrollment = TakenCourse.objects.get(
            student=self.student,
            course=self.course,
            semester=self.semester,
        )

        allocation = CourseAllocation.objects.create(
            lecturer=self.lecturer,
            session=self.session,
        )
        allocation.courses.add(self.course)
        self.client.force_login(self.lecturer)
        score_response = self.client.post(
            reverse("add_score_for", args=(self.course.pk,)),
            {str(enrollment.pk): ["18", "18", "18", "18", "18"]},
        )
        self.assertEqual(score_response.status_code, 302)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.total, Decimal("90.00"))
        self.assertEqual(enrollment.grade, "A+")
        self.assertTrue(
            Result.objects.filter(
                student=self.student,
                session=self.session.session,
                semester=self.semester.semester,
            ).exists()
        )

        self.client.force_login(self.registrar)
        placement_response = self.client.post(
            reverse("clinical:placement_create"),
            {
                "student": self.student.pk,
                "ward": self.ward.pk,
                "semester": self.semester.pk,
                "supervisor": self.lecturer.pk,
                "starts_on": "2026-10-01",
                "ends_on": "2026-12-01",
                "learning_objectives": "Demonstrate safe mental health assessment.",
            },
        )
        self.assertEqual(placement_response.status_code, 302)
        placement = ClinicalPlacement.objects.get(student=self.student)
        activate_placement_response = self.client.post(
            reverse("clinical:placement_change_status", args=(placement.pk,)),
            {
                "status": ClinicalPlacement.Status.IN_PROGRESS,
                "reason": "Rotation commenced.",
            },
        )
        self.assertEqual(activate_placement_response.status_code, 302)

        self.client.force_login(self.student_user)
        log_response = self.client.post(
            reverse("clinical:placement_detail", args=(placement.pk,)),
            {
                "date": "2026-10-18",
                "shift": ClinicalLogEntry.Shift.DAY,
                "hours": "8.00",
                "competency": "Mental status examination",
                "activity": "Completed a supervised assessment.",
                "reflection": "Applied therapeutic communication.",
            },
        )
        self.assertEqual(log_response.status_code, 302)
        self.assertEqual(placement.log_entries.count(), 1)

        FeeCategory.objects.create(
            name="First semester tuition",
            amount=Decimal("1200.00"),
            semester=self.semester,
        )
        self.client.force_login(self.finance_manager)
        invoice_response = self.client.post(
            reverse("finance:generate_semester_invoices"),
            {"due_date": "2026-12-01"},
        )
        self.assertEqual(invoice_response.status_code, 302)
        invoice = Invoice.objects.get(student=self.student, semester=self.semester)
        payment_response = self.client.post(
            reverse("finance:record_invoice_payment", args=(invoice.pk,)),
            {
                "amount": "300.00",
                "payment_date": "2026-10-18",
                "method": InvoicePayment.Method.BANK,
                "reference": "LIFECYCLE-001",
            },
        )
        self.assertEqual(payment_response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("300.00"))
        self.assertEqual(invoice.status, "partial")
        self.assertEqual(invoice.payments.count(), 1)

        self.client.force_login(self.student_user)
        student_invoices_response = self.client.get(
            reverse("finance:student_invoices")
        )
        self.assertEqual(student_invoices_response.status_code, 200)
        self.assertContains(student_invoices_response, f"INV{invoice.pk:05d}")

        admin = User.objects.create_superuser(
            username="lifecycle-admin",
            email="lifecycle-admin@example.test",
            password="lifecycle-test-password",
        )
        self.client.force_login(admin)
        report_response = self.client.get(
            reverse("institutional_reports"),
            {"semester": self.semester.pk},
        )
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.context["student_count"], 1)
        self.assertEqual(report_response.context["admission_total"], 1)
        self.assertEqual(report_response.context["active_enrollment_count"], 1)
        self.assertEqual(report_response.context["pass_count"], 1)
        self.assertEqual(report_response.context["clinical_placement_count"], 1)
        self.assertEqual(report_response.context["invoice_total"], Decimal("1200.00"))
        self.assertEqual(report_response.context["amount_paid"], Decimal("300.00"))
        self.assertEqual(report_response.context["outstanding"], Decimal("900.00"))


@override_settings(DEBUG=True)
class DemoDataCommandTests(TransactionTestCase):
    def test_dry_run_rolls_back_seeded_records(self):
        output = StringIO()
        call_command("seed_demo_data", "--dry-run", stdout=output)
        self.assertEqual(User.objects.filter(username__startswith="demo_").count(), 0)
        self.assertIn("rolled back", output.getvalue())

    def test_demo_seed_is_idempotent(self):
        call_command("seed_demo_data", stdout=StringIO())
        self.assertTrue(User.objects.filter(username="demo_student").exists())
        student = Student.objects.get(student__username="demo_student")
        self.assertFalse(student.student.has_usable_password())
        self.assertFalse(
            User.objects.get(username="demo_supervisor").has_usable_password()
        )
        self.assertEqual(student.program.title, "DEMO - Psychiatric Nursing")
        self.assertEqual(
            TakenCourse.objects.filter(student=student, semester=student.semester).count(),
            2,
        )
        scores = list(
            TakenCourse.objects.filter(student=student, semester=student.semester)
            .order_by("course__code")
            .values_list("total", "grade")
        )
        self.assertEqual(
            scores,
            [(Decimal("85.05"), "A"), (Decimal("75.50"), "B+")],
        )
        self.assertEqual(
            Result.objects.get(student=student, session=student.semester.session.session).gpa,
            3.75,
        )
        self.assertEqual(
            AttendanceRecord.objects.filter(student=student).count(),
            2,
        )
        self.assertTrue(
            Application.objects.filter(
                application_number="DEMO-APP-001",
                linked_student=student,
                status=Application.Status.ACCEPTED,
            ).exists()
        )
        invoice = Invoice.objects.get(student=student, status="partial")
        self.assertEqual(invoice.total_amount, Decimal("1200000.00"))
        self.assertEqual(invoice.paid_amount, Decimal("300000.00"))
        self.assertEqual(invoice.balance, Decimal("900000.00"))
        self.assertEqual(invoice.payments.get().amount, Decimal("300000.00"))
        self.assertEqual(
            Staff.objects.get(user__username="demo_finance").qualification,
            "DEMO - Diploma in Business Administration",
        )
        self.assertEqual(ClinicalPlacement.objects.filter(student=student).count(), 1)
        quotation = PurchaseQuotation.objects.get(reference="DEMO-QUOTE-0001")
        self.assertEqual(quotation.total_amount, Decimal("825000.00"))
        self.assertEqual(quotation.items_total, Decimal("825000.00"))
        order = PurchaseOrder.objects.get(
            requisition__title="DEMO - Ward training supplies"
        )
        self.assertEqual(order.total_amount, Decimal("850000.00"))
        self.assertEqual(order.items_total, Decimal("850000.00"))

        seeded_counts = (
            User.objects.filter(username__startswith="demo_").count(),
            Student.objects.count(),
            Course.objects.filter(code__startswith="DEMO-").count(),
            Invoice.objects.count(),
            PurchaseQuotation.objects.count(),
        )
        call_command("seed_demo_data", stdout=StringIO())
        self.assertEqual(
            seeded_counts,
            (
                User.objects.filter(username__startswith="demo_").count(),
                Student.objects.count(),
                Course.objects.filter(code__startswith="DEMO-").count(),
                Invoice.objects.count(),
                PurchaseQuotation.objects.count(),
            ),
        )

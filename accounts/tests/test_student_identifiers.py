from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Student, User
from core.forms import StudentIdentifierSettingsForm
from core.models import SiteSettings
from course.models import Program


@override_settings(LANGUAGE_CODE="en")
class StudentIdentifierTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(
            title="Psychiatric Nursing",
            code="PSN",
        )
        self.settings = SiteSettings.get_settings()

    def create_student(self, username, **student_fields):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="test-password",
        )
        return Student.objects.create(student=user, **student_fields)

    def test_registration_number_uses_program_intake_month_year_and_sequence(self):
        student = self.create_student(
            "new-student",
            program=self.program,
            cohort="August 2026",
        )

        self.assertEqual(
            student.registration_number,
            f"PSN-Aug-26-{student.pk:06}",
        )

    def test_registration_number_uses_configured_format_and_preserves_existing_value(self):
        self.settings.student_registration_number_format = (
            "STU-{year_short}-{intake_month_short}-{sequence:06}"
        )
        self.settings.save(update_fields=("student_registration_number_format",))
        student = self.create_student(
            "formatted-student",
            program=self.program,
            cohort="January 2027",
            registration_number="OLD-REG-123",
        )

        student.cohort = "March 2028"
        student.save()
        self.assertEqual(student.registration_number, "OLD-REG-123")

        student.registration_number = ""
        student.save()
        self.assertEqual(
            student.registration_number,
            f"STU-28-Mar-{student.pk:06}",
        )

    def test_registration_format_requires_a_sequence(self):
        form = StudentIdentifierSettingsForm(
            instance=self.settings,
            data={"student_registration_number_format": "{program_code}-{year_short}"},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("student_registration_number_format", form.errors)

    def test_administrator_can_update_registration_number_format(self):
        administrator = User.objects.create_superuser(
            username="identifier-admin",
            email="identifier-admin@example.test",
            password="test-password",
        )
        self.client.force_login(administrator)
        url = reverse("site_settings_student_ids")
        page = self.client.get(url)
        self.assertEqual(
            page.status_code,
            200,
            f"URL={url}; superuser={administrator.is_superuser}; "
            f"redirect={page.get('Location')}; "
            f"resolved={getattr(page.wsgi_request, 'resolver_match', None)}; "
            f"body={page.content.decode()}",
        )

        response = self.client.post(
            url,
            {
                "student_registration_number_format":
                    "{program_code}-{intake_month_short}-{year_short}-{sequence:06}"
            },
        )

        self.assertRedirects(response, url)
        self.settings.refresh_from_db()
        self.assertEqual(
            self.settings.student_registration_number_format,
            "{program_code}-{intake_month_short}-{year_short}-{sequence:06}",
        )

    def test_user_directory_displays_the_saved_user_id(self):
        administrator = User.objects.create_superuser(
            username="user-id-admin",
            email="user-id-admin@example.test",
            password="test-password",
        )
        user = User.objects.create_user(
            username="visible-id-user",
            email="visible-id-user@example.test",
            password="test-password",
        )
        self.client.force_login(administrator)

        response = self.client.get(reverse("user_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"<td>{user.pk}</td>", html=True)

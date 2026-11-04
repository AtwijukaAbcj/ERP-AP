from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.forms import FacultyLecturerAddForm, StaffAddForm
from accounts.models import User
from course.models import Faculty


@override_settings(LANGUAGE_CODE="en")
class LecturerAssignmentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="lecturer-admin",
            email="admin@example.test",
            password="Strong-test-password-2026!",
        )
        self.user = User.objects.create_user(
            username="new-lecturer",
            email="lecturer@example.test",
            password="Strong-test-password-2026!",
        )
        self.existing_lecturer = User.objects.create_user(
            username="existing-lecturer",
            email="existing@example.test",
            password="Strong-test-password-2026!",
            is_lecturer=True,
        )
        self.faculty = Faculty.objects.create(name="Engineering")

    def test_staff_add_form_assigns_existing_user_without_creating_an_account(self):
        form = StaffAddForm(
            data={"user": self.user.pk, "faculty": self.faculty.pk}
        )

        self.assertTrue(form.is_valid(), form.errors)
        user_count = User.objects.count()
        lecturer = form.save()

        selected_label = form.fields["user"].label_from_instance(lecturer)
        self.assertEqual(User.objects.count(), user_count)
        self.assertEqual(lecturer.pk, self.user.pk)
        self.assertTrue(lecturer.is_lecturer)
        self.assertEqual(lecturer.faculty, self.faculty)
        self.assertIn(lecturer.email, selected_label)
        self.assertIn(lecturer.get_full_name, selected_label)
        self.assertNotIn(self.existing_lecturer, form.fields["user"].queryset)

    def test_faculty_form_assigns_selected_user_to_current_faculty(self):
        form = FacultyLecturerAddForm(
            data={"user": self.user.pk},
            faculty=self.faculty,
        )

        self.assertTrue(form.is_valid(), form.errors)
        lecturer = form.save()

        self.assertEqual(lecturer.pk, self.user.pk)
        self.assertTrue(lecturer.is_lecturer)
        self.assertEqual(lecturer.faculty, self.faculty)

    def test_admin_can_assign_an_existing_user_as_lecturer(self):
        self.client.force_login(self.admin)
        user_count = User.objects.count()

        response = self.client.get(reverse("add_lecturer"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="user"')
        self.assertContains(response, self.user.email)

        response = self.client.post(
            reverse("add_lecturer"),
            {"user": self.user.pk, "faculty": self.faculty.pk},
        )

        self.assertRedirects(response, reverse("lecturer_list"))
        self.assertEqual(User.objects.count(), user_count)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_lecturer)

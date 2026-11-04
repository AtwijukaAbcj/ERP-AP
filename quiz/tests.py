from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from course.models import Course
from .models import Quiz, Sitting


@override_settings(LANGUAGE_CODE="en")
class QuizMarkingUrlTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="quiz-admin",
            email="quiz-admin@example.test",
            password="Strong-test-password-2026!",
        )
        self.student = User.objects.create_user(
            username="quiz-student",
            email="quiz-student@example.test",
            password="Strong-test-password-2026!",
        )
        self.course = Course.objects.create(
            title="Django",
            code="DJANGO-101",
            semester="First",
        )
        self.quiz = Quiz.objects.create(
            course=self.course,
            title="Django Fundamentals",
        )
        self.sitting = Sitting.objects.create(
            user=self.student,
            quiz=self.quiz,
            course=self.course,
            question_order="",
            question_list="",
            current_score=0,
            complete=True,
        )
        self.client.force_login(self.admin)

    def test_marking_list_renders_detail_link_for_completed_sitting(self):
        response = self.client.get(reverse("quiz_marking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("quiz_marking_detail", kwargs={"pk": self.sitting.pk}),
        )

    def test_marking_detail_route_resolves_and_displays_sitting(self):
        response = self.client.get(
            reverse("quiz_marking_detail", kwargs={"pk": self.sitting.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.quiz.title)
        self.assertContains(response, self.student.username)

from decimal import Decimal

from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import Student, User
from core.models import Semester, Session
from course.models import Course, CourseAllocation, Program
from result.models import TakenCourse
from result.views import add_score_for


class EnrollmentResultIntegrationTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.student_user = User.objects.create_user(
            username="result-student",
            password="test-password",
            is_student=True,
        )
        self.student = Student.objects.create(
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
            credit=3,
        )
        self.previous_session = Session.objects.create(session="2025/2026")
        self.current_session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        self.previous_semester = Semester.objects.create(
            semester="First",
            session=self.previous_session,
        )
        self.current_semester = Semester.objects.create(
            semester="First",
            session=self.current_session,
            is_current_semester=True,
        )

    def test_gpa_uses_current_semester_attempt_and_cgpa_keeps_prior_attempt(self):
        TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.previous_semester,
            assignment=Decimal("45.00"),
        )
        current_attempt = TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.current_semester,
            assignment=Decimal("80.00"),
        )

        self.assertEqual(current_attempt.calculate_gpa(), Decimal("3.75"))
        self.assertEqual(current_attempt.calculate_cgpa(), Decimal("2.38"))


@override_settings(LANGUAGE_CODE="en")
class AssessmentScoreEntryTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Nursing")
        self.student_user = User.objects.create_user(
            username="score-student",
            password="test-password",
            is_student=True,
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        self.lecturer = User.objects.create_user(
            username="score-lecturer",
            password="test-password",
            is_lecturer=True,
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
            title="Foundations",
            code="NUR101",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        allocation = CourseAllocation.objects.create(
            lecturer=self.lecturer,
            session=self.session,
        )
        allocation.courses.add(self.course)
        self.enrollment = TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.semester,
        )
        self.client.force_login(self.lecturer)

    def test_score_entry_page_is_routed_and_scoped_to_allocated_course(self):
        response = self.client.get(
            reverse("add_score_for", args=(self.course.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Foundations")
        self.assertContains(response, f'name="{self.enrollment.pk}"')

    def test_score_entry_uses_the_active_semesters_linked_session(self):
        other_session = Session.objects.create(
            session="2025/2026",
            is_current_session=True,
        )
        Session.objects.filter(pk=self.session.pk).update(
            is_current_session=False
        )

        score_list_response = self.client.get(reverse("add_score"))
        score_form_response = self.client.get(
            reverse("add_score_for", args=(self.course.pk,))
        )

        self.assertEqual(score_list_response.status_code, 200)
        self.assertContains(score_list_response, "Foundations")
        self.assertEqual(score_form_response.status_code, 200)
        self.assertContains(score_form_response, "Foundations")
        self.assertContains(score_form_response, f'name="{self.enrollment.pk}"')
        self.assertTrue(other_session.is_current_session)

    def test_student_assessment_hub_is_reachable(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("assessment_hub"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessment")

    def test_scores_are_saved_and_result_gpa_is_updated(self):
        response = self.client.post(
            reverse("add_score_for", args=(self.course.pk,)),
            {str(self.enrollment.pk): ["10", "10", "10", "5", "60"]},
        )

        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total, Decimal("95.00"))
        self.assertEqual(self.enrollment.grade, "A+")
        result = self.student.result_set.get(
            session=self.session.session,
            semester=self.semester.semester,
        )
        self.assertEqual(result.gpa, 4.0)
        self.assertEqual(result.cgpa, 4.0)

    def test_post_cannot_change_another_course_enrollment(self):
        other_course = Course.objects.create(
            title="Other Course",
            code="NUR102",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        other_enrollment = TakenCourse.objects.create(
            student=self.student,
            course=other_course,
            semester=self.semester,
        )

        response = self.client.post(
            reverse("add_score_for", args=(self.course.pk,)),
            {str(other_enrollment.pk): ["10", "10", "10", "5", "60"]},
        )

        self.assertEqual(response.status_code, 302)
        other_enrollment.refresh_from_db()
        self.assertEqual(other_enrollment.total, Decimal("0.00"))

    def test_unallocated_course_cannot_be_viewed_or_graded(self):
        other_course = Course.objects.create(
            title="Unallocated Course",
            code="NUR103",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )

        request = RequestFactory().get(
            reverse("add_score_for", args=(other_course.pk,))
        )
        request.user = self.lecturer

        with self.assertRaises(Http404):
            add_score_for(request, other_course.pk)

    def test_invalid_scores_are_rejected_without_partial_updates(self):
        response = self.client.post(
            reverse("add_score_for", args=(self.course.pk,)),
            {str(self.enrollment.pk): ["10", "10", "10", "5", "101"]},
        )

        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total, Decimal("0.00"))

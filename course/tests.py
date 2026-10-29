from decimal import Decimal
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import DepartmentHead, Student, User
from core.models import Semester
from result.models import TakenCourse
from .models import Course, CourseOffer, Program


@override_settings(LANGUAGE_CODE="en")
class CourseRegistrationTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.other_program = Program.objects.create(title="General Nursing")
        self.semester = Semester.objects.create(
            semester="First",
            is_current_semester=True,
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
        self.other_program_course = Course.objects.create(
            title="General Nursing Practice",
            code="GNS101",
            program=self.other_program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        self.client.force_login(self.student_user)

    def test_registration_page_offers_only_eligible_current_semester_courses(self):
        response = self.client.get(reverse("course_registration"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.code)
        self.assertNotContains(response, self.other_program_course.code)

    def test_student_can_register_for_an_eligible_course(self):
        response = self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        enrollment = TakenCourse.objects.get(student=self.student, course=self.course)
        self.assertEqual(enrollment.semester, self.semester)

    def test_posted_arbitrary_field_does_not_register_a_course(self):
        self.client.post(
            reverse("course_registration"),
            {str(self.course.pk): "on"},
        )

        self.assertFalse(TakenCourse.objects.exists())

    def test_student_cannot_register_for_another_programs_course(self):
        response = self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.other_program_course.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TakenCourse.objects.exists())

    def test_student_cannot_register_for_a_future_year_or_other_semester_course(self):
        future_year_course = Course.objects.create(
            title="Advanced Mental Health",
            code="PMN201",
            program=self.program,
            level="Bachelor",
            year=2,
            semester="First",
        )
        other_semester_course = Course.objects.create(
            title="Clinical Foundations",
            code="PMN102",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="Second",
        )

        response = self.client.post(
            reverse("course_registration"),
            {
                "course_ids": [
                    str(future_year_course.pk),
                    str(other_semester_course.pk),
                ]
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TakenCourse.objects.exists())

    def test_registration_and_drop_obey_the_academic_calendar(self):
        self.semester.registration_close_date = date(2000, 1, 1)
        self.semester.add_drop_open_date = date(2099, 1, 1)
        self.semester.add_drop_close_date = date(2099, 12, 31)
        self.semester.save()

        response = self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TakenCourse.objects.exists())

        enrollment = TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.semester,
        )
        self.client.post(
            reverse("course_drop"),
            {"enrollment_ids": [str(enrollment.pk)]},
        )
        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_dropped)

    def test_department_head_course_offerings_limit_registration(self):
        unoffered_course = Course.objects.create(
            title="Psychiatric Nursing Practice",
            code="PMN102",
            program=self.program,
            level="Bachelor",
            year=1,
            semester="First",
            credit=3,
        )
        department_head_user = User.objects.create_user(
            username="academic-department-head",
            password="test-password",
        )
        department_head = DepartmentHead.objects.create(
            user=department_head_user,
            department=self.program,
        )
        offer = CourseOffer.objects.create(
            dep_head=department_head,
            semester=self.semester,
        )
        offer.courses.add(self.course)

        response = self.client.get(reverse("course_registration"))
        self.assertContains(response, self.course.code)
        self.assertNotContains(response, unoffered_course.code)

        self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(unoffered_course.pk)]},
        )
        self.assertFalse(TakenCourse.objects.exists())

    def test_repeat_submission_cannot_create_duplicate_active_enrollment(self):
        url = reverse("course_registration")
        payload = {"course_ids": [str(self.course.pk)]}
        self.client.post(url, payload)
        self.client.post(url, payload)

        self.assertEqual(
            TakenCourse.objects.filter(student=self.student, course=self.course).count(),
            1,
        )

    def test_inactive_student_cannot_register(self):
        self.student.status = Student.Status.SUSPENDED
        self.student.save(update_fields=("status",))

        self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )

        self.assertFalse(TakenCourse.objects.exists())

    def test_drop_preserves_grades_and_allows_a_new_active_attempt(self):
        enrollment = TakenCourse.objects.create(
            student=self.student,
            course=self.course,
            semester=self.semester,
            assignment=Decimal("12.00"),
        )

        response = self.client.post(
            reverse("course_drop"),
            {"enrollment_ids": [str(enrollment.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.is_dropped)
        self.assertEqual(enrollment.assignment, Decimal("12.00"))
        self.assertEqual(enrollment.dropped_by, self.student_user)
        self.assertIsNotNone(enrollment.dropped_at)
        self.assertFalse(TakenCourse.objects.filter(pk=enrollment.pk).exists())
        self.assertTrue(TakenCourse.all_objects.filter(pk=enrollment.pk).exists())

        self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )
        self.assertEqual(
            TakenCourse.objects.filter(student=self.student, course=self.course).count(),
            1,
        )
        previous_semester = Semester.objects.get(pk=self.semester.pk)
        previous_semester.is_current_semester = False
        previous_semester.save(update_fields=("is_current_semester",))
        next_semester = Semester.objects.create(
            semester="First",
            is_current_semester=True,
        )
        self.client.post(
            reverse("course_registration"),
            {"course_ids": [str(self.course.pk)]},
        )
        self.assertEqual(
            TakenCourse.objects.filter(student=self.student, course=self.course).count(),
            2,
        )
        self.assertTrue(
            TakenCourse.objects.filter(
                student=self.student,
                course=self.course,
                semester=next_semester,
            ).exists()
        )

    def test_student_cannot_drop_another_students_enrollment(self):
        other_user = User.objects.create_user(
            username="other-academic-student",
            password="test-password",
            is_student=True,
        )
        other_student = Student.objects.create(
            student=other_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        enrollment = TakenCourse.objects.create(
            student=other_student,
            course=self.course,
        )

        self.client.post(
            reverse("course_drop"),
            {"enrollment_ids": [str(enrollment.pk)]},
        )

        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_dropped)

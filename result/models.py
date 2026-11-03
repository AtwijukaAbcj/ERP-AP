from decimal import Decimal
from django.conf import settings

from django.db import models
from django.db.models import Q
from django.urls import reverse

from accounts.models import Student
from core.models import Semester
from course.models import Course

A_PLUS = "A+"
A = "A"
A_MINUS = "A-"
B_PLUS = "B+"
B = "B"
B_MINUS = "B-"
C_PLUS = "C+"
C = "C"
C_MINUS = "C-"
D = "D"
F = "F"
NG = "NG"

GRADE_CHOICES = (
    (A_PLUS, "A+"),
    (A, "A"),
    (A_MINUS, "A-"),
    (B_PLUS, "B+"),
    (B, "B"),
    (B_MINUS, "B-"),
    (C_PLUS, "C+"),
    (C, "C"),
    (C_MINUS, "C-"),
    (D, "D"),
    (F, "F"),
    (NG, "NG"),
)

PASS = "PASS"
FAIL = "FAIL"

COMMENT_CHOICES = (
    (PASS, "PASS"),
    (FAIL, "FAIL"),
)

GRADE_BOUNDARIES = [
    (90, A_PLUS),
    (85, A),
    (80, A_MINUS),
    (75, B_PLUS),
    (70, B),
    (65, B_MINUS),
    (60, C_PLUS),
    (55, C),
    (50, C_MINUS),
    (45, D),
    (0, F),
]

GRADE_POINT_MAPPING = {
    A_PLUS: 4.0,
    A: 4.0,
    A_MINUS: 3.75,
    B_PLUS: 3.5,
    B: 3.0,
    B_MINUS: 2.75,
    C_PLUS: 2.5,
    C: 2.0,
    C_MINUS: 1.75,
    D: 1.0,
    F: 0.0,
    NG: 0.0,
}


class ActiveTakenCourseManager(models.Manager):
    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().filter(is_dropped=False)


class TakenCourse(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="taken_courses"
    )
    semester = models.ForeignKey(
        Semester,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_enrollments",
    )
    is_dropped = models.BooleanField(default=False, db_index=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    dropped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dropped_course_enrollments",
    )
    assignment = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    mid_exam = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    quiz = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    attendance = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    final_exam = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    grade = models.CharField(
        choices=GRADE_CHOICES, max_length=2, blank=True, editable=False
    )
    point = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), editable=False
    )
    comment = models.CharField(
        choices=COMMENT_CHOICES, max_length=200, blank=True, editable=False
    )

    objects = ActiveTakenCourseManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("student", "course", "semester"),
                condition=Q(is_dropped=False, semester__isnull=False),
                name="unique_active_student_course_semester",
            )
        ]

    def get_absolute_url(self):
        return reverse("course_detail", kwargs={"slug": self.course.slug})

    def __str__(self):
        return f"{self.course.title} ({self.course.code})"

    def get_total(self):
        return sum(
            [
                Decimal(self.assignment),
                Decimal(self.mid_exam),
                Decimal(self.quiz),
                Decimal(self.attendance),
                Decimal(self.final_exam),
            ]
        )

    def get_grade(self):
        total = self.total
        for boundary, grade in GRADE_BOUNDARIES:
            if total >= boundary:
                return grade
        return NG

    def get_comment(self):
        if self.grade in [F, NG]:
            return FAIL
        return PASS

    def get_point(self):
        credit = self.course.credit
        grade_point = GRADE_POINT_MAPPING.get(self.grade, 0.0)
        return Decimal(credit) * Decimal(grade_point)

    def save(self, *args, **kwargs):
        self.total = self.get_total()
        self.grade = self.get_grade()
        self.point = self.get_point()
        self.comment = self.get_comment()
        super().save(*args, **kwargs)

    def calculate_gpa(self):
        current_semester = Semester.objects.filter(is_current_semester=True).first()
        if not current_semester:
            return Decimal("0.00")

        taken_courses = TakenCourse.objects.filter(
            student=self.student,
            course__programs=self.student.program,
            course__semester=current_semester.semester,
        ).filter(Q(semester=current_semester) | Q(semester__isnull=True))

        total_points = sum(tc.point for tc in taken_courses)
        total_credits = sum(tc.course.credit for tc in taken_courses)

        if total_credits > 0:
            gpa = total_points / Decimal(total_credits)
            return round(gpa, 2)
        return Decimal("0.00")

    def calculate_cgpa(self):
        taken_courses = TakenCourse.objects.filter(student=self.student)

        total_points = sum(tc.point for tc in taken_courses)
        total_credits = sum(tc.course.credit for tc in taken_courses)

        if total_credits > 0:
            cgpa = total_points / Decimal(total_credits)
            return round(cgpa, 2)
        return Decimal("0.00")


class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    gpa = models.FloatField(null=True)
    cgpa = models.FloatField(null=True)
    semester = models.CharField(max_length=100, choices=settings.SEMESTER_CHOICES)
    session = models.CharField(max_length=100, blank=True, null=True)
    level = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Result for {self.student} - Semester: {self.semester}, Level: {self.level}"


# ########################################################
# Assessment Configuration Model
# ########################################################
class AssessmentConfig(models.Model):
    """Configures assessment weights and settings for each course"""
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='assessment_config')
    
    # Weight configurations (should total 100%)
    assignment_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    mid_exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))
    quiz_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    attendance_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    final_exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("60.00"))
    
    # Max scores for each component
    assignment_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    mid_exam_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))
    quiz_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    attendance_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    final_exam_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("60.00"))
    
    # Total expected classes for attendance
    total_classes = models.PositiveIntegerField(default=30)
    
    # Enable/disable components
    assignment_enabled = models.BooleanField(default=True)
    mid_exam_enabled = models.BooleanField(default=True)
    quiz_enabled = models.BooleanField(default=True)
    attendance_enabled = models.BooleanField(default=True)
    final_exam_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Assessment Configuration"
        verbose_name_plural = "Assessment Configurations"
    
    def __str__(self):
        return f"Assessment Config for {self.course}"
    
    def get_total_weight(self):
        total = Decimal("0.00")
        if self.assignment_enabled:
            total += self.assignment_weight
        if self.mid_exam_enabled:
            total += self.mid_exam_weight
        if self.quiz_enabled:
            total += self.quiz_weight
        if self.attendance_enabled:
            total += self.attendance_weight
        if self.final_exam_enabled:
            total += self.final_exam_weight
        return total


# ########################################################
# Attendance Tracking Model
# ########################################################
ATTENDANCE_STATUS = (
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('late', 'Late'),
    ('excused', 'Excused'),
)

class AttendanceRecord(models.Model):
    """Tracks individual class attendance for students"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='present')
    remarks = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='recorded_attendance'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        unique_together = ['student', 'course', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.student} - {self.course} - {self.date} - {self.status}"


class ClassSession(models.Model):
    """Represents a scheduled class session"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='class_sessions')
    date = models.DateField()
    topic = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Class Session"
        verbose_name_plural = "Class Sessions"
        unique_together = ['course', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.course} - {self.date}"


# ########################################################
# Course Assignment Model
# ########################################################
ASSIGNMENT_TYPE = (
    ('assignment', 'Assignment'),
    ('coursework', 'Coursework'),
    ('project', 'Project'),
    ('lab', 'Lab Work'),
)

class CourseAssignment(models.Model):
    """Represents an assignment/coursework for a course"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE, default='assignment')
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"))
    due_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Course Assignment"
        verbose_name_plural = "Course Assignments"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.course}"


class AssignmentSubmission(models.Model):
    """Student submission for an assignment"""
    assignment = models.ForeignKey(CourseAssignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='graded_assignments'
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Assignment Submission"
        verbose_name_plural = "Assignment Submissions"
        unique_together = ['assignment', 'student']
    
    def __str__(self):
        return f"{self.student} - {self.assignment}"
    
    def save(self, *args, **kwargs):
        # Check if submission is late
        if self.assignment.due_date and self.submitted_at:
            self.is_late = self.submitted_at > self.assignment.due_date
        super().save(*args, **kwargs)

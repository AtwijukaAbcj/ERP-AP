from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError

from course.models import Course
from accounts.models import Student


# ########################################################
# Assignment Group - For weighted grade calculation
# ########################################################

class AssignmentGroup(models.Model):
    """
    Canvas-style assignment groups for weighted grade calculation.
    e.g., Homework 20%, Quizzes 30%, Midterm 20%, Final 30%
    """
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='assignment_groups'
    )
    name = models.CharField(max_length=100)
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage (0-100)"
    )
    position = models.PositiveIntegerField(default=0)
    drop_lowest = models.PositiveIntegerField(
        default=0,
        help_text="Number of lowest scores to drop from this group"
    )
    drop_highest = models.PositiveIntegerField(
        default=0,
        help_text="Number of highest scores to drop from this group"
    )

    class Meta:
        ordering = ['position', 'name']
        unique_together = ['course', 'name']

    def __str__(self):
        return f"{self.name} ({self.weight}%)"

    def get_student_average(self, student):
        """Calculate student's weighted average for this group"""
        submissions = AssignmentSubmission.objects.filter(
            assignment__group=self,
            student=student,
            score__isnull=False
        ).select_related('assignment')
        
        if not submissions.exists():
            return None
        
        scores = []
        for sub in submissions:
            if sub.assignment.points_possible > 0:
                percentage = (sub.score / sub.assignment.points_possible) * 100
                scores.append(percentage)
        
        if not scores:
            return None
        
        # Sort and drop lowest/highest if configured
        scores.sort()
        if self.drop_lowest > 0:
            scores = scores[self.drop_lowest:]
        if self.drop_highest > 0 and len(scores) > self.drop_highest:
            scores = scores[:-self.drop_highest]
        
        if not scores:
            return None
        
        return sum(scores) / len(scores)


# ########################################################
# Student Groups - For group assignments
# ########################################################

class StudentGroup(models.Model):
    """Groups of students for collaborative assignments"""
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE,
        related_name='student_groups'
    )
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(
        Student, 
        related_name='assignment_groups_member'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['course', 'name']

    def __str__(self):
        return f"{self.name} - {self.course.title}"


# ########################################################
# Rubric - For criteria-based grading
# ########################################################

class Rubric(models.Model):
    """Reusable rubric template for grading"""
    title = models.CharField(max_length=200)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='rubrics',
        null=True,
        blank=True,
        help_text="Leave blank for global rubrics"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    @property
    def total_points(self):
        return sum(c.points for c in self.criteria.all())


class RubricCriterion(models.Model):
    """Individual criterion within a rubric"""
    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.CASCADE,
        related_name='criteria'
    )
    description = models.CharField(max_length=500)
    points = models.DecimalField(max_digits=6, decimal_places=2)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']
        verbose_name_plural = "Rubric criteria"

    def __str__(self):
        return f"{self.description[:50]} ({self.points} pts)"


class RubricRating(models.Model):
    """Rating levels for a criterion (e.g., Excellent, Good, Fair, Poor)"""
    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    description = models.CharField(max_length=200)
    points = models.DecimalField(max_digits=6, decimal_places=2)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-points', 'position']

    def __str__(self):
        return f"{self.description} ({self.points} pts)"


# ########################################################
# Assignment - Main assessment model
# ########################################################

class Assignment(models.Model):
    """
    Canvas-style assignment with flexible submission types
    """
    # Assignment Types
    TYPE_ASSIGNMENT = 'assignment'
    TYPE_QUIZ = 'quiz'
    TYPE_DISCUSSION = 'discussion'
    TYPE_PROJECT = 'project'
    TYPE_ATTENDANCE = 'attendance'
    TYPE_EXTERNAL = 'external'
    
    ASSIGNMENT_TYPE_CHOICES = [
        (TYPE_ASSIGNMENT, 'Assignment'),
        (TYPE_QUIZ, 'Quiz/Exam'),
        (TYPE_DISCUSSION, 'Discussion'),
        (TYPE_PROJECT, 'Project'),
        (TYPE_ATTENDANCE, 'Attendance/Participation'),
        (TYPE_EXTERNAL, 'External Tool'),
    ]
    
    # Submission Types
    SUBMISSION_NONE = 'none'
    SUBMISSION_ONLINE = 'online'
    SUBMISSION_PAPER = 'paper'
    SUBMISSION_EXTERNAL = 'external'
    
    SUBMISSION_TYPE_CHOICES = [
        (SUBMISSION_NONE, 'No Submission'),
        (SUBMISSION_ONLINE, 'Online'),
        (SUBMISSION_PAPER, 'On Paper'),
        (SUBMISSION_EXTERNAL, 'External Tool'),
    ]
    
    # Online Submission Options
    ONLINE_TEXT = 'text'
    ONLINE_FILE = 'file'
    ONLINE_URL = 'url'
    
    ONLINE_ENTRY_CHOICES = [
        (ONLINE_TEXT, 'Text Entry'),
        (ONLINE_FILE, 'File Upload'),
        (ONLINE_URL, 'Website URL'),
    ]
    
    # Grading Types
    GRADE_POINTS = 'points'
    GRADE_PERCENTAGE = 'percentage'
    GRADE_LETTER = 'letter'
    GRADE_PASS_FAIL = 'pass_fail'
    GRADE_COMPLETE = 'complete'
    GRADE_NOT_GRADED = 'not_graded'
    
    GRADING_TYPE_CHOICES = [
        (GRADE_POINTS, 'Points'),
        (GRADE_PERCENTAGE, 'Percentage'),
        (GRADE_LETTER, 'Letter Grade'),
        (GRADE_PASS_FAIL, 'Pass/Fail'),
        (GRADE_COMPLETE, 'Complete/Incomplete'),
        (GRADE_NOT_GRADED, 'Not Graded'),
    ]
    
    # File type choices
    FILE_TYPE_PDF = 'pdf'
    FILE_TYPE_DOC = 'doc'
    FILE_TYPE_ARCHIVE = 'archive'
    FILE_TYPE_IMAGE = 'image'
    FILE_TYPE_CODE = 'code'
    FILE_TYPE_ANY = 'any'
    
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_PDF, 'PDF only'),
        (FILE_TYPE_DOC, 'Documents (doc, docx, pdf, txt)'),
        (FILE_TYPE_ARCHIVE, 'Archives (zip, rar, 7z)'),
        (FILE_TYPE_IMAGE, 'Images (jpg, png, gif)'),
        (FILE_TYPE_CODE, 'Code files'),
        (FILE_TYPE_ANY, 'Any file type'),
    ]
    
    # Basic Info
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='canvas_assignments'
    )
    group = models.ForeignKey(
        AssignmentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default=TYPE_ASSIGNMENT
    )
    
    # Submission Settings
    submission_type = models.CharField(
        max_length=20,
        choices=SUBMISSION_TYPE_CHOICES,
        default=SUBMISSION_ONLINE
    )
    online_entry_options = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed online submission types: text, file, url"
    )
    allowed_file_types = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        default=FILE_TYPE_ANY,
        blank=True
    )
    max_file_size = models.PositiveIntegerField(
        default=50,
        help_text="Maximum file size in MB"
    )
    allowed_attempts = models.PositiveIntegerField(
        default=1,
        help_text="0 for unlimited attempts"
    )
    
    # Grading Settings
    grading_type = models.CharField(
        max_length=20,
        choices=GRADING_TYPE_CHOICES,
        default=GRADE_POINTS
    )
    points_possible = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=100
    )
    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    
    # Link to Quiz (for quiz-type assignments)
    linked_quiz = models.ForeignKey(
        'quiz.Quiz',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_assignments',
        help_text="Link to an existing quiz for auto-grading integration"
    )
    
    # Group Assignment Settings
    is_group_assignment = models.BooleanField(default=False)
    group_category = models.ForeignKey(
        StudentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_assignments',
        help_text="If group assignment, select the student group"
    )
    
    # Dates
    due_date = models.DateTimeField(null=True, blank=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    
    # Late Policy
    accept_late_submissions = models.BooleanField(default=True)
    late_penalty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage deducted per day late"
    )
    max_late_days = models.PositiveIntegerField(
        default=0,
        help_text="Maximum days late accepted (0 for unlimited)"
    )
    
    # Display Settings
    published = models.BooleanField(default=False)
    show_rubric_to_students = models.BooleanField(default=True)
    anonymous_grading = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_assignments'
    )

    class Meta:
        ordering = ['due_date', 'title']

    def __str__(self):
        return f"{self.title} - {self.course.title}"

    def get_allowed_extensions(self):
        """Return list of allowed file extensions"""
        extension_map = {
            self.FILE_TYPE_PDF: ['.pdf'],
            self.FILE_TYPE_DOC: ['.doc', '.docx', '.pdf', '.txt', '.rtf', '.odt'],
            self.FILE_TYPE_ARCHIVE: ['.zip', '.rar', '.7z', '.tar', '.gz'],
            self.FILE_TYPE_IMAGE: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
            self.FILE_TYPE_CODE: ['.py', '.js', '.java', '.c', '.cpp', '.html', '.css', '.php', '.rb'],
            self.FILE_TYPE_ANY: [],
        }
        return extension_map.get(self.allowed_file_types, [])

    @property
    def is_available(self):
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return self.published

    @property
    def is_past_due(self):
        if not self.due_date:
            return False
        return timezone.now() > self.due_date

    def calculate_late_penalty(self, submission_date):
        """Calculate late penalty for a submission"""
        if not self.due_date or submission_date <= self.due_date:
            return Decimal('0')
        
        if not self.accept_late_submissions:
            return Decimal('100')  # Full penalty
        
        days_late = (submission_date - self.due_date).days + 1
        
        if self.max_late_days > 0 and days_late > self.max_late_days:
            return Decimal('100')  # Not accepted
        
        penalty = Decimal(str(days_late)) * self.late_penalty_percent
        return min(penalty, Decimal('100'))

    def get_submission_count(self):
        return self.submissions.count()

    def get_graded_count(self):
        return self.submissions.filter(score__isnull=False).count()

    def get_average_score(self):
        graded = self.submissions.filter(score__isnull=False)
        if not graded.exists():
            return None
        total = sum(s.score for s in graded)
        return total / graded.count()


# ########################################################
# Assignment Submission
# ########################################################

def submission_file_path(instance, filename):
    """Generate file path for submissions"""
    return f"submissions/{instance.assignment.course.slug}/{instance.assignment.id}/{instance.student.student.username}/{filename}"


class AssignmentSubmission(models.Model):
    """Student submission for an assignment"""
    
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_LATE = 'late'
    STATUS_GRADED = 'graded'
    STATUS_RETURNED = 'returned'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_LATE, 'Late'),
        (STATUS_GRADED, 'Graded'),
        (STATUS_RETURNED, 'Returned for Revision'),
    ]
    
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='canvas_submissions'
    )
    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="For group assignments"
    )
    
    # Submission Content
    text_entry = models.TextField(blank=True)
    file_upload = models.FileField(
        upload_to=submission_file_path,
        null=True,
        blank=True
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    url_submission = models.URLField(blank=True)
    
    # Submission Tracking
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Grading
    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    grade = models.CharField(max_length=5, blank=True)  # For letter grades
    late_penalty_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_assignment_submissions'
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        # Allow multiple attempts if configured
        unique_together = ['assignment', 'student', 'attempt_number']

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"

    def save(self, *args, **kwargs):
        # Track file info
        if self.file_upload and hasattr(self.file_upload, 'name'):
            if not self.original_filename:
                self.original_filename = self.file_upload.name
            if hasattr(self.file_upload, 'size'):
                self.file_size = self.file_upload.size
        
        # Check for late submission
        if self.submitted_at and self.assignment.due_date:
            if self.submitted_at > self.assignment.due_date:
                self.status = self.STATUS_LATE
                self.late_penalty_applied = self.assignment.calculate_late_penalty(self.submitted_at)
        
        super().save(*args, **kwargs)

    def submit(self):
        """Mark submission as submitted"""
        self.submitted_at = timezone.now()
        if self.assignment.due_date and self.submitted_at > self.assignment.due_date:
            self.status = self.STATUS_LATE
            self.late_penalty_applied = self.assignment.calculate_late_penalty(self.submitted_at)
        else:
            self.status = self.STATUS_SUBMITTED
        self.save()

    @property
    def final_score(self):
        """Score after late penalty"""
        if self.score is None:
            return None
        penalty_multiplier = (100 - self.late_penalty_applied) / 100
        return self.score * Decimal(str(penalty_multiplier))

    @property
    def percentage(self):
        """Score as percentage of points possible"""
        if self.final_score is None:
            return None
        if self.assignment.points_possible == 0:
            return 0
        return (self.final_score / self.assignment.points_possible) * 100


# ########################################################
# Rubric Assessment - For criterion-based grading
# ########################################################

class RubricAssessment(models.Model):
    """Rubric-based assessment for a submission"""
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='rubric_assessments'
    )
    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE
    )
    rating = models.ForeignKey(
        RubricRating,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    points_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0
    )
    comments = models.TextField(blank=True)

    class Meta:
        unique_together = ['submission', 'criterion']

    def __str__(self):
        return f"{self.submission} - {self.criterion}"


# ########################################################
# Grade Calculation Utility
# ########################################################

class CourseGradeCalculator:
    """Utility class to calculate weighted course grades"""
    
    def __init__(self, course, student):
        self.course = course
        self.student = student
    
    def calculate_weighted_grade(self):
        """Calculate student's weighted grade for the course"""
        groups = AssignmentGroup.objects.filter(course=self.course)
        
        if not groups.exists():
            return self._calculate_simple_average()
        
        total_weight = Decimal('0')
        weighted_sum = Decimal('0')
        
        for group in groups:
            avg = group.get_student_average(self.student)
            if avg is not None:
                weighted_sum += Decimal(str(avg)) * (group.weight / 100)
                total_weight += group.weight
        
        if total_weight == 0:
            return None
        
        # Normalize if weights don't sum to 100
        return weighted_sum * (100 / total_weight)
    
    def _calculate_simple_average(self):
        """Fallback: simple average of all assignments"""
        submissions = AssignmentSubmission.objects.filter(
            assignment__course=self.course,
            student=self.student,
            score__isnull=False
        ).select_related('assignment')
        
        if not submissions.exists():
            return None
        
        total_percentage = Decimal('0')
        count = 0
        
        for sub in submissions:
            if sub.assignment.points_possible > 0:
                percentage = (sub.final_score / sub.assignment.points_possible) * 100
                total_percentage += percentage
                count += 1
        
        return total_percentage / count if count > 0 else None
    
    def get_letter_grade(self, percentage=None):
        """Convert percentage to letter grade"""
        from result.models import GRADE_BOUNDARIES
        
        if percentage is None:
            percentage = self.calculate_weighted_grade()
        
        if percentage is None:
            return 'NG'
        
        for threshold, grade in GRADE_BOUNDARIES:
            if percentage >= threshold:
                return grade
        
        return 'F'
    
    def get_grade_breakdown(self):
        """Get detailed breakdown of grades by assignment group"""
        groups = AssignmentGroup.objects.filter(course=self.course)
        breakdown = []
        
        for group in groups:
            submissions = AssignmentSubmission.objects.filter(
                assignment__group=group,
                student=self.student
            ).select_related('assignment')
            
            assignments_data = []
            for sub in submissions:
                assignments_data.append({
                    'assignment': sub.assignment,
                    'score': sub.final_score,
                    'possible': sub.assignment.points_possible,
                    'percentage': sub.percentage,
                    'graded': sub.score is not None,
                })
            
            breakdown.append({
                'group': group,
                'weight': group.weight,
                'average': group.get_student_average(self.student),
                'assignments': assignments_data,
            })
        
        return breakdown

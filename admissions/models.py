from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ApplicationStatus(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "application status"
        verbose_name_plural = "application statuses"

    def __str__(self):
        return self.name

    @classmethod
    def label_for(cls, code):
        return cls.objects.filter(code=code).values_list("name", flat=True).first() or code


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        SCREENING = "screening", "Under review"
        SHORTLISTED = "shortlisted", "Shortlisted"
        WAITLISTED = "waitlisted", "Waitlisted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    application_number = models.CharField(max_length=20, unique=True, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=60)
    address = models.TextField(blank=True)
    next_of_kin_name = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=60, blank=True)
    program = models.ForeignKey(
        "course.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )
    intake = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=20)
    previous_education = models.TextField(blank=True)
    status = models.CharField(
        max_length=50,
        default=Status.SUBMITTED,
        db_index=True,
    )
    decision_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_admission_applications",
    )
    linked_student = models.OneToOneField(
        "accounts.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_application",
    )

    class Meta:
        ordering = ("-created_at",)

    def get_status_display(self):
        return ApplicationStatus.label_for(self.status)

    def clean(self):
        if self.date_of_birth and self.date_of_birth > timezone.localdate():
            raise ValidationError(
                {"date_of_birth": "Date of birth cannot be in the future."}
            )

    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = f"TEMP-{uuid4().hex}"
            super().save(*args, **kwargs)
            self.application_number = (
                f"APP-{timezone.localdate().year}-{self.pk:06d}"
            )
            super().save(update_fields=("application_number",))
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_number}: {self.first_name} {self.last_name}"


class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=50)
    to_status = models.CharField(max_length=50)
    comment = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)

    def get_from_status_display(self):
        return ApplicationStatus.label_for(self.from_status)

    def get_to_status_display(self):
        return ApplicationStatus.label_for(self.to_status)

    def __str__(self):
        return f"{self.application.application_number}: {self.from_status} -> {self.to_status}"


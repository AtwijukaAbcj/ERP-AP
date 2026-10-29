from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Ward(models.Model):
    name = models.CharField(max_length=150)
    facility = models.CharField(max_length=200, default="Butabika Hospital")
    description = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("facility", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("facility", "name"),
                name="unique_clinical_ward_per_facility",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.facility}"


class ClinicalPlacement(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.PROTECT,
        related_name="clinical_placements",
    )
    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="placements",
    )
    semester = models.ForeignKey(
        "core.Semester",
        on_delete=models.PROTECT,
        related_name="clinical_placements",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supervised_clinical_placements",
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )
    learning_objectives = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_clinical_placements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-starts_on", "student__registration_number")
        indexes = [
            models.Index(fields=("ward", "status", "starts_on", "ends_on")),
            models.Index(fields=("student", "status")),
        ]

    def clean(self):
        errors = {}
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "The end date must be on or after the start date."
        if self.student_id and self.student.status != self.student.Status.ACTIVE:
            errors["student"] = "Only active students can be assigned to a placement."
        if self.ward_id and not self.ward.is_active:
            errors["ward"] = "Choose an active clinical ward."
        if self.supervisor_id and not self.supervisor.is_active:
            errors["supervisor"] = "The clinical supervisor must be active."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.student} - {self.ward} ({self.starts_on} to {self.ends_on})"


class PlacementStatusHistory(models.Model):
    placement = models.ForeignKey(
        ClinicalPlacement,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=20, choices=ClinicalPlacement.Status.choices)
    to_status = models.CharField(max_length=20, choices=ClinicalPlacement.Status.choices)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_placement_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)


class ClinicalLogEntry(models.Model):
    class Shift(models.TextChoices):
        DAY = "day", "Day"
        EVENING = "evening", "Evening"
        NIGHT = "night", "Night"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        VERIFIED = "verified", "Verified"
        RETURNED = "returned", "Returned to student"

    placement = models.ForeignKey(
        ClinicalPlacement,
        on_delete=models.PROTECT,
        related_name="log_entries",
    )
    date = models.DateField()
    shift = models.CharField(max_length=10, choices=Shift.choices)
    hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0.25), MaxValueValidator(24)],
    )
    competency = models.CharField(max_length=200)
    activity = models.TextField()
    reflection = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    supervisor_feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_clinical_log_entries",
    )

    class Meta:
        ordering = ("-date", "-submitted_at")
        indexes = [models.Index(fields=("placement", "status", "date"))]

    def clean(self):
        errors = {}
        if self.placement_id:
            if self.date and not (
                self.placement.starts_on <= self.date <= self.placement.ends_on
            ):
                errors["date"] = "The log date must fall within the placement dates."
            if self.placement.status != ClinicalPlacement.Status.IN_PROGRESS:
                errors["placement"] = "Logs can only be submitted during an active placement."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.placement.student} - {self.competency} ({self.date})"

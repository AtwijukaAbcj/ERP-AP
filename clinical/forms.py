from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounts.models import Student, User
from core.models import Semester

from .models import ClinicalLogEntry, ClinicalPlacement, Ward


class WardForm(forms.ModelForm):
    class Meta:
        model = Ward
        fields = ("name", "facility", "description", "capacity", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "facility": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ClinicalPlacementForm(forms.ModelForm):
    class Meta:
        model = ClinicalPlacement
        fields = (
            "student",
            "ward",
            "semester",
            "supervisor",
            "starts_on",
            "ends_on",
            "learning_objectives",
        )
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "ward": forms.Select(attrs={"class": "form-select"}),
            "semester": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "starts_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "ends_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "learning_objectives": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status=Student.Status.ACTIVE,
            student__is_active=True,
        ).select_related("student", "program")
        self.fields["ward"].queryset = Ward.objects.filter(is_active=True)
        self.fields["semester"].queryset = Semester.objects.select_related("session")
        self.fields["supervisor"].queryset = User.objects.filter(
            is_active=True,
        ).filter(
            Q(is_staff=True)
            | Q(is_lecturer=True)
            | Q(is_dep_head=True)
            | Q(is_registrar=True)
        ).order_by("last_name", "first_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        for field, error in self.validate_conflicts(cleaned_data).items():
            self.add_error(field, error)
        return cleaned_data

    def validate_conflicts(self, cleaned_data=None):
        cleaned_data = cleaned_data or self.cleaned_data
        errors = {}
        student = cleaned_data.get("student")
        ward = cleaned_data.get("ward")
        starts_on = cleaned_data.get("starts_on")
        ends_on = cleaned_data.get("ends_on")
        if not all((student, ward, starts_on, ends_on)) or ends_on < starts_on:
            return errors

        overlapping_student_placements = ClinicalPlacement.objects.filter(
            student=student,
            starts_on__lte=ends_on,
            ends_on__gte=starts_on,
            status__in=(
                ClinicalPlacement.Status.PLANNED,
                ClinicalPlacement.Status.IN_PROGRESS,
            ),
        )
        if self.instance.pk:
            overlapping_student_placements = overlapping_student_placements.exclude(
                pk=self.instance.pk
            )
        if overlapping_student_placements.exists():
            errors["student"] = (
                "This student already has a planned or active placement during these dates."
            )

        overlapping_ward_placements = ClinicalPlacement.objects.filter(
            ward=ward,
            starts_on__lte=ends_on,
            ends_on__gte=starts_on,
            status__in=(
                ClinicalPlacement.Status.PLANNED,
                ClinicalPlacement.Status.IN_PROGRESS,
            ),
        )
        if self.instance.pk:
            overlapping_ward_placements = overlapping_ward_placements.exclude(
                pk=self.instance.pk
            )
        if overlapping_ward_placements.count() >= ward.capacity:
            errors["ward"] = (
                "This ward has no available placement capacity during these dates."
            )
        return errors


class ClinicalLogEntryForm(forms.ModelForm):
    class Meta:
        model = ClinicalLogEntry
        fields = ("date", "shift", "hours", "competency", "activity", "reflection")
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "shift": forms.Select(attrs={"class": "form-select"}),
            "hours": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.25", "max": "24", "step": "0.25"}
            ),
            "competency": forms.TextInput(attrs={"class": "form-control"}),
            "activity": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "reflection": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, placement, **kwargs):
        self.placement = placement
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.placement.status != ClinicalPlacement.Status.IN_PROGRESS:
            raise ValidationError("Logs can only be submitted during an active placement.")
        date = cleaned_data.get("date")
        if date and not self.placement.starts_on <= date <= self.placement.ends_on:
            self.add_error("date", "The log date must fall within the placement dates.")
        return cleaned_data

from django import forms
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Student
from course.models import AcademicYear
from core.models import Semester, Session
from course.models import Program
from .models import (
    Application,
    ApplicationStatus,
)


class AdmissionApplicationForm(forms.ModelForm):
    intake = forms.ChoiceField(choices=())
    academic_year = forms.ChoiceField(choices=())

    class Meta:
        model = Application
        fields = (
            "first_name",
            "last_name",
            "date_of_birth",
            "email",
            "phone",
            "address",
            "next_of_kin_name",
            "next_of_kin_phone",
            "program",
            "intake",
            "academic_year",
            "previous_education",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "previous_education": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["intake"].widget.attrs["class"] = "form-select"
        self.fields["academic_year"].widget.attrs["class"] = "form-select"
        self.fields["program"].queryset = Program.objects.order_by("title")

        months = (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
        intake_choices = [(month, f"{month} Intake") for month in months]
        existing_intakes = set(
            Application.objects.order_by()
            .values_list("intake", flat=True)
            .distinct()
        )
        intake_choices.extend(
            (value, value)
            for value in sorted(existing_intakes.difference(months))
            if value
        )
        self.fields["intake"].choices = [("", "Select an intake"), *intake_choices]

        academic_years = {
            (f"{year}/{year + 1}", f"{year}/{year + 1}")
            for year in range(
                timezone.localdate().year - 2,
                timezone.localdate().year + 6,
            )
        }
        academic_years.update(
            (value, value)
            for value in Session.objects.order_by()
            .values_list("session", flat=True)
            .distinct()
            if value
            and len(value) == 9
            and value[4] == "/"
            and value[:4].isdigit()
            and value[5:].isdigit()
        )
        academic_years.update(
            (value, value)
            for value in Application.objects.order_by()
            .values_list("academic_year", flat=True)
            .distinct()
            if value
            and len(value) == 9
            and value[4] == "/"
            and value[:4].isdigit()
            and value[5:].isdigit()
        )
        self.fields["academic_year"].choices = [
            ("", "Select an academic year"),
            *sorted(academic_years, reverse=True),
        ]


class ApplicationStatusForm(forms.Form):
    status = forms.ChoiceField(choices=())
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, application, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = list(
            ApplicationStatus.objects.filter(is_active=True)
            .order_by("sort_order", "name")
            .values_list("code", "name")
        )
        self.fields["status"].initial = application.status
        self.fields["status"].widget.attrs["class"] = "form-select"
        self.fields["comment"].widget.attrs["class"] = "form-control"


class ApplicationStatusSettingsForm(forms.ModelForm):
    class Meta:
        model = ApplicationStatus
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["class"] = "form-control"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        code = slugify(name)
        if not code:
            raise forms.ValidationError("Enter a status name containing letters or numbers.")
        if len(code) > 50:
            raise forms.ValidationError("The status name is too long to create a status code.")
        existing = ApplicationStatus.objects.filter(code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(
                "A status with this name already exists. Choose a different name."
            )
        return name

    def save(self, commit=True):
        status = super().save(commit=False)
        if not status.pk:
            status.code = slugify(self.cleaned_data["name"])
            status.sort_order = (
                ApplicationStatus.objects.aggregate(max_order=Max("sort_order"))[
                    "max_order"
                ]
                or 0
            ) + 1
        if commit:
            status.save()
        return status


class LinkStudentForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none())

    def __init__(self, application, *args, **kwargs):
        self.application = application
        super().__init__(*args, **kwargs)
        queryset = Student.objects.select_related("student", "program").filter(
            status=Student.Status.ACTIVE
        )
        if application.program_id:
            queryset = queryset.filter(program_id=application.program_id)
        self.fields["student"].queryset = queryset.order_by("student__last_name")
        self.fields["student"].widget.attrs["class"] = "form-select"

        linked_ids = (
            Application.objects.exclude(pk=application.pk)
            .filter(linked_student__isnull=False)
            .values_list("linked_student_id", flat=True)
        )
        self.fields["student"].queryset = self.fields["student"].queryset.exclude(
            pk__in=linked_ids
        )

    def clean_student(self):
        student = self.cleaned_data["student"]
        if Application.objects.filter(linked_student=student).exists():
            raise forms.ValidationError("This student is already linked to an application.")
        applicant_name = (
            self.application.first_name.strip().casefold(),
            self.application.last_name.strip().casefold(),
        )
        student_name = (
            student.student.first_name.strip().casefold(),
            student.student.last_name.strip().casefold(),
        )
        if applicant_name != student_name:
            raise forms.ValidationError(
                "The selected student's name does not match the accepted applicant."
            )
        return student


class ProvisionAcceptedStudentForm(forms.Form):
    year = forms.TypedChoiceField(
        coerce=int,
        choices=(),
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.order_by("session__session", "semester"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"].choices = tuple(
            (academic_year.number, str(academic_year.number))
            for academic_year in AcademicYear.objects.all()
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

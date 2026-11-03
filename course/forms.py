from django import forms
from django.core.validators import RegexValidator
from accounts.models import User
from .models import (
    AcademicYear,
    Course,
    CourseAllocation,
    Program,
    ProgramLevel,
    Upload,
    UploadVideo,
)
from .models import Faculty

class ProgramForm(forms.ModelForm):
    level = forms.ModelChoiceField(
        queryset=ProgramLevel.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    code = forms.CharField(
        max_length=20,
        required=True,
        label="Program Code",
        help_text="A short unique code used in student registration numbers.",
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
                message="Use letters and numbers, with optional hyphens.",
            )
        ],
    )

    class Meta:
        model = Program
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update({"class": "form-control"})
        self.fields["code"].widget.attrs.update({"class": "form-control", "autocapitalize": "characters"})
        self.fields["summary"].widget.attrs.update({"class": "form-control"})
        self.fields["faculty"].widget.attrs.update({"class": "form-select"})
        self.fields["level"].widget.attrs.update({"class": "form-select"})

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        programs = Program.objects.filter(code__iexact=code)
        if self.instance.pk:
            programs = programs.exclude(pk=self.instance.pk)
        if programs.exists():
            raise forms.ValidationError("A program with this code already exists.")
        return code


class CourseAddForm(forms.ModelForm):
    programs = forms.ModelMultipleChoiceField(
        queryset=Program.objects.all(),
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        label="Programs",
    )
    year = forms.TypedChoiceField(
        coerce=int,
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Course
        fields = (
            "title",
            "code",
            "credit",
            "summary",
            "programs",
            "year",
            "semester",
            "is_elective",
        )

    def __init__(self, *args, **kwargs):
        program = kwargs.pop("program", None)
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.update({"class": "form-control"})
        self.fields["code"].widget.attrs.update({"class": "form-control"})
        self.fields["credit"].widget.attrs.update({"class": "form-control"})
        self.fields["summary"].widget.attrs.update({"class": "form-control"})
        self.fields["semester"].widget.attrs.update({"class": "form-control"})
        self.fields["is_elective"].widget.attrs.update({"class": "form-check-input"})
        self.fields["year"].choices = (
            ("", "Select a year"),
            *(
                (academic_year.number, str(academic_year.number))
                for academic_year in AcademicYear.objects.all()
            ),
        )

        if program:
            self.fields["programs"].initial = [program.pk]
        programs = Program.objects.select_related("level")
        if user and getattr(user, "is_faculty_admin", False):
            programs = programs.filter(faculty=user.faculty)
        self.fields["programs"].queryset = programs.order_by("title")


class ProgramLevelForm(forms.ModelForm):
    class Meta:
        model = ProgramLevel
        fields = ("name",)
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ("number",)
        widgets = {
            "number": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "step": "1"}
            )
        }



class CourseAllocationForm(forms.ModelForm):
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),  # default to none, will be set in __init__
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "browser-default checkbox"}
        ),
        required=True,
    )
    lecturer = forms.ModelChoiceField(
        queryset=User.objects.none(),  # default to none, will be set in __init__
        widget=forms.Select(attrs={"class": "browser-default custom-select"}),
        label="lecturer",
    )

    class Meta:
        model = CourseAllocation
        fields = ["lecturer", "courses"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # ✅ Get the logged-in user
        super(CourseAllocationForm, self).__init__(*args, **kwargs)

        if user and getattr(user, 'is_faculty_admin', False):
            self.fields["lecturer"].queryset = User.objects.filter(is_lecturer=True, faculty=user.faculty)
            self.fields["courses"].queryset = Course.objects.filter(
                programs__faculty=user.faculty
            ).distinct().order_by("programs__level__name", "year", "title")
        elif user and getattr(user, 'is_superuser', False):
            self.fields["lecturer"].queryset = User.objects.filter(is_lecturer=True)
            self.fields["courses"].queryset = Course.objects.all().order_by("title")
        else:
            # Default empty if the user is not a faculty admin or superuser
            self.fields["lecturer"].queryset = User.objects.none()
            self.fields["courses"].queryset = Course.objects.none()


class EditCourseAllocationForm(forms.ModelForm):
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all().order_by("title"),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    lecturer = forms.ModelChoiceField(
        queryset=User.objects.filter(is_lecturer=True),
        widget=forms.Select(attrs={"class": "browser-default custom-select"}),
        label="lecturer",
    )

    class Meta:
        model = CourseAllocation
        fields = ["lecturer", "courses"]

    def __init__(self, *args, **kwargs):
        #    user = kwargs.pop('user')
        super(EditCourseAllocationForm, self).__init__(*args, **kwargs)
        self.fields["lecturer"].queryset = User.objects.filter(is_lecturer=True)


# Upload files to specific course
class UploadFormFile(forms.ModelForm):
    class Meta:
        model = Upload
        fields = (
            "title",
            "file",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update({"class": "form-control"})
        self.fields["file"].widget.attrs.update({"class": "form-control"})


# Upload video to specific course
class UploadFormVideo(forms.ModelForm):
    class Meta:
        model = UploadVideo
        fields = (
            "title",
            "video",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update({"class": "form-control"})
        self.fields["video"].widget.attrs.update({"class": "form-control"})


class FacultyForm(forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Faculty Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
        }
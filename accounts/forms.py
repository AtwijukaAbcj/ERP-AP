from django import forms
from django.db import transaction
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone
import random
import string

from core.models import Semester
from course.models import Program, Faculty
from .models import Role, Permission, RolePermission, UserPermission, User, Student, StudentDocument, Parent, RELATION_SHIP, LEVEL, GENDERS, RegistrarModulePermission, REGISTRAR_MODULES, ACTIVE_MODULE_CHOICES


class UserAddForm(UserCreationForm):
    ACCOUNT_TYPE_CHOICES = (
        ("user", "General User"),
        ("student", "Student"),
        ("lecturer", "Lecturer"),
        ("finance", "Finance"),
        ("registrar", "Registrar"),
    )

    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        initial="user",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Account type",
        help_text="Choose the user's account type. Assign permission roles separately after creating the account.",
    )

    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Username",
        required=True,
    )

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="First Name",
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Last Name",
    )

    gender = forms.CharField(
        widget=forms.Select(
            choices=GENDERS,
            attrs={"class": "browser-default custom-select form-control"},
        ),
    )

    address = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Address",
    )

    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Mobile No.",
    )

    email = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Email",
    )

    password1 = forms.CharField(
        max_length=30,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Password",
    )

    password2 = forms.CharField(
        max_length=30,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Password Confirmation",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "gender",
            "address",
            "phone",
            "password1",
            "password2",
        )

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)
        account_type = self.cleaned_data["account_type"]
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        user.phone = self.cleaned_data.get("phone")
        user.address = self.cleaned_data.get("address")
        user.email = self.cleaned_data.get("email")
        user.is_student = account_type == "student"
        user.is_lecturer = account_type == "lecturer"
        user.is_finance = account_type == "finance"
        user.is_registrar = account_type == "registrar"

        if commit:
            user.save()
            if user.is_student:
                Student.objects.create(student=user)

        return user


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "slug", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ["name", "code", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "code": "Code name",
        }


class RolePermissionForm(forms.Form):
    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        widget=forms.RadioSelect,
        label="Role",
    )
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Permissions",
        help_text="Select every permission to grant to this role.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.order_by("name")
        permissions = Permission.objects.order_by("module", "name")
        self.fields["permissions"].queryset = permissions

        grouped_choices = {}
        for permission in permissions:
            module = permission.module
            if not module and permission.code:
                module = (
                    permission.code.split(".", 1)[0]
                    .split("__", 1)[0]
                    .replace("_", " ")
                    .title()
                )
            module = module or "Other"
            grouped_choices.setdefault(module, []).append(
                (permission.pk, f"{permission.name} ({permission.code})")
            )
        self.fields["permissions"].choices = [
            (module, choices)
            for module, choices in grouped_choices.items()
        ]

    def save(self):
        role = self.cleaned_data["role"]
        created_role_permissions = []
        for permission in self.cleaned_data["permissions"]:
            role_permission, created = RolePermission.objects.get_or_create(
                role=role,
                permission=permission,
            )
            if created:
                created_role_permissions.append(role_permission)
        return created_role_permissions


class UserPermissionForm(forms.ModelForm):
    class Meta:
        model = UserPermission
        fields = ["user", "permission", "effect", "reason"]
        widgets = {
            "user": forms.Select(attrs={"class": "form-control"}),
            "permission": forms.Select(attrs={"class": "form-control"}),
            "effect": forms.Select(attrs={"class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(
            is_superuser=False,
        ).order_by("username")
        self.fields["permission"].queryset = Permission.objects.order_by("code")


class StaffAddForm(UserAddForm):
    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Username",
        required=False,
    )

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="First Name",
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Last Name",
    )

    gender = forms.CharField(
        widget=forms.Select(
            choices=GENDERS,
            attrs={"class": "browser-default custom-select form-control"},
        ),
    )

    address = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Address",
    )

    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Mobile No.",
    )

    email = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "text", "class": "form-control"}),
        label="Email",
    )

    faculty = forms.ModelChoiceField(
        queryset=Faculty.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Faculty",
    )

    password1 = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "password", "class": "form-control"}),
        label="Password",
        required=False,
    )

    password2 = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"type": "password", "class": "form-control"}),
        label="Password Confirmation",
        required=False,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "gender",
            "address",
            "phone",
            "faculty",
        )

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_lecturer = True
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        user.phone = self.cleaned_data.get("phone")
        user.address = self.cleaned_data.get("address")
        user.email = self.cleaned_data.get("email")
        user.faculty = self.cleaned_data.get("faculty")

        if commit:
            user.save()

        return user


class UserRolesForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all permission roles this user should receive.",
    )

    class Meta:
        model = User
        fields = ("roles",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Role.objects.order_by("name")
        if self.instance.pk:
            self.initial["roles"] = self.instance.roles.all()

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        selected_roles = self.cleaned_data["roles"]
        user.role = selected_roles.first() if selected_roles else None
        if commit:
            user.save(update_fields=("role",))
            self.save_m2m()
        return user
# accounts/forms.py
# accounts/forms.py

# accounts/forms.py
# forms.py

# accounts/forms.py

# accounts/forms.py

class FacultyLecturerAddForm(UserCreationForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(choices=GENDERS, widget=forms.Select(attrs={"class": "form-control"}))
    phone = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["first_name", "last_name", "email", "gender", "phone", "address"]

    @transaction.atomic
    def save(self, commit=True, faculty=None):
        user = super().save(commit=False)
        user.username = f"lec{get_random_string(5)}"
        user.set_password(get_random_string(8))
        user.is_lecturer = True
        user.faculty = faculty
        if commit:
            user.save()
        return user

class StudentEditForm(forms.ModelForm):
    registration_number = forms.CharField(
        max_length=60,
        label="Registration Number",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    level = forms.ChoiceField(
        choices=LEVEL,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    year = forms.ChoiceField(
        choices=settings.YEARS,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    program = forms.ModelChoiceField(
        queryset=Program.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    cohort = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    admission_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    expected_completion_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    next_of_kin_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    next_of_kin_phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "gender", "phone", "address", "picture"]

    def __init__(self, *args, **kwargs):
        self.student_instance = kwargs.pop("student_instance", None)
        super().__init__(*args, **kwargs)
        if self.student_instance:
            self.fields["registration_number"].initial = self.student_instance.registration_number
            self.fields["level"].initial = self.student_instance.level
            self.fields["year"].initial = self.student_instance.year
            self.fields["semester"].initial = self.student_instance.semester
            self.fields["program"].initial = self.student_instance.program
            self.fields["date_of_birth"].initial = self.student_instance.date_of_birth
            self.fields["cohort"].initial = self.student_instance.cohort
            self.fields["admission_date"].initial = self.student_instance.admission_date
            self.fields["expected_completion_date"].initial = (
                self.student_instance.expected_completion_date
            )
            self.fields["next_of_kin_name"].initial = self.student_instance.next_of_kin_name
            self.fields["next_of_kin_phone"].initial = (
                self.student_instance.next_of_kin_phone
            )

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if self.student_instance:
            self.student_instance.registration_number = self.cleaned_data.get("registration_number")
            self.student_instance.level = self.cleaned_data.get("level")
            self.student_instance.year = self.cleaned_data.get("year")
            self.student_instance.semester = self.cleaned_data.get("semester")
            self.student_instance.program = self.cleaned_data.get("program")
            self.student_instance.date_of_birth = self.cleaned_data.get("date_of_birth")
            self.student_instance.cohort = self.cleaned_data.get("cohort", "")
            self.student_instance.admission_date = self.cleaned_data.get("admission_date")
            self.student_instance.expected_completion_date = (
                self.cleaned_data.get("expected_completion_date")
            )
            self.student_instance.next_of_kin_name = self.cleaned_data.get(
                "next_of_kin_name", ""
            )
            self.student_instance.next_of_kin_phone = self.cleaned_data.get(
                "next_of_kin_phone", ""
            )
            if commit:
                self.student_instance.save()
        return user

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth >= timezone.localdate():
            raise forms.ValidationError("Date of birth must be in the past.")
        return date_of_birth

    def clean_registration_number(self):
        registration_number = self.cleaned_data.get("registration_number")
        if not registration_number:
            return registration_number
        students = Student.objects.filter(registration_number=registration_number)
        if self.student_instance:
            students = students.exclude(pk=self.student_instance.pk)
        if students.exists():
            raise forms.ValidationError("This registration number is already in use.")
        return registration_number

    def clean(self):
        cleaned_data = super().clean()
        admission_date = cleaned_data.get("admission_date")
        completion_date = cleaned_data.get("expected_completion_date")
        if admission_date and completion_date and completion_date < admission_date:
            self.add_error(
                "expected_completion_date",
                "Expected completion date must be on or after the admission date.",
            )
        return cleaned_data

class FinanceAddForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="First Name",
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Last Name",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        label="Email",
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Phone",
    )
    address = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Address",
    )
    gender = forms.ChoiceField(
        choices=GENDERS,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Gender",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["first_name", "last_name", "email", "phone", "address", "gender"]

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_finance = True

        # Auto-generate username and password
        random_username = f"fin{random.randint(1000, 9999)}"
        random_password = "".join(random.choices(string.ascii_letters + string.digits, k=8))

        user.username = random_username
        user.set_password(random_password)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data["phone"]
        user.address = self.cleaned_data["address"]
        user.gender = self.cleaned_data["gender"]

        if commit:
            user.save()
            self.generated_username = random_username
            self.generated_password = random_password

        return user

class StudentAddForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(choices=GENDERS, widget=forms.Select(attrs={"class": "form-control"}))
    address = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    phone = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    level = forms.ChoiceField(choices=LEVEL, widget=forms.Select(attrs={"class": "form-control"}))
    year = forms.ChoiceField(choices=settings.YEARS, widget=forms.Select(attrs={"class": "form-control"}))
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
    )
    program = forms.ModelChoiceField(queryset=Program.objects.all(), widget=forms.Select(attrs={"class": "form-control"}))
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    cohort = forms.CharField(
        required=True,
        label="Intake / Cohort",
        help_text="Enter the intake month and academic year, for example August 2026.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    admission_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    expected_completion_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    next_of_kin_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    next_of_kin_phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'address', 'phone']

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = f"stu{get_random_string(6)}"
        password = get_random_string(10)
        user.set_password(password)
        user.is_student = True
        if commit:
            user.save()
            Student.objects.create(
                student=user,
                level=self.cleaned_data.get("level"),
                year=self.cleaned_data.get("year"),
                semester=self.cleaned_data.get("semester"),
                program=self.cleaned_data.get("program"),
                date_of_birth=self.cleaned_data.get("date_of_birth"),
                cohort=self.cleaned_data.get("cohort", ""),
                admission_date=self.cleaned_data.get("admission_date"),
                expected_completion_date=self.cleaned_data.get(
                    "expected_completion_date"
                ),
                next_of_kin_name=self.cleaned_data.get("next_of_kin_name", ""),
                next_of_kin_phone=self.cleaned_data.get("next_of_kin_phone", ""),
            )
            # TODO: Send email to student with `user.username` and `password`
        return user

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth >= timezone.localdate():
            raise forms.ValidationError("Date of birth must be in the past.")
        return date_of_birth

    def clean(self):
        cleaned_data = super().clean()
        admission_date = cleaned_data.get("admission_date")
        completion_date = cleaned_data.get("expected_completion_date")
        if admission_date and completion_date and completion_date < admission_date:
            self.add_error(
                "expected_completion_date",
                "Expected completion date must be on or after the admission date.",
            )
        return cleaned_data


class StudentDocumentForm(forms.ModelForm):
    class Meta:
        model = StudentDocument
        fields = ("category", "title", "file")
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if uploaded_file.size > 10 * 1024 * 1024:
            raise forms.ValidationError("File size must not exceed 10 MB.")
        return uploaded_file


class StudentStatusForm(forms.Form):
    status = forms.ChoiceField(choices=(), widget=forms.Select(attrs={"class": "form-select"}))
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, student, *args, **kwargs):
        from .student_services import STATUS_TRANSITIONS

        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (status, Student.Status(status).label)
            for status in STATUS_TRANSITIONS[student.status]
        ]


class ProfileUpdateForm(UserChangeForm):
    email = forms.EmailField(
        widget=forms.TextInput(
            attrs={
                "type": "email",
                "class": "form-control",
            }
        ),
        label="Email Address",
    )

    first_name = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="First Name",
    )

    last_name = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Last Name",
    )

    gender = forms.CharField(
        widget=forms.Select(
            choices=GENDERS,
            attrs={
                "class": "browser-default custom-select form-control",
            },
        ),
    )

    phone = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Phone No.",
    )
    faculty = forms.ModelChoiceField(
    queryset=Faculty.objects.all(),
    required=True,
    widget=forms.Select(attrs={"class": "form-control"}),
    label="Faculty",
    )
    address = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Address / city",
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "gender",
            "email",
            "phone",
            "address",
            "picture",
        ]


class ProgramUpdateForm(UserChangeForm):
    program = forms.ModelChoiceField(
        queryset=Program.objects.all(),
        widget=forms.Select(
            attrs={"class": "browser-default custom-select form-control"}
        ),
        label="Program",
    )

    class Meta:
        model = Student
        fields = ["program"]


class EmailValidationOnForgotPassword(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data["email"]
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            msg = "There is no user registered with the specified E-mail address. "
            self.add_error("email", msg)
            return email


class ParentAddForm(UserCreationForm):
    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Username",
    )
    address = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Address",
    )

    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Mobile No.",
    )

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="First name",
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "class": "form-control",
            }
        ),
        label="Last name",
    )

    email = forms.EmailField(
        widget=forms.TextInput(
            attrs={
                "type": "email",
                "class": "form-control",
            }
        ),
        label="Email Address",
    )

    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(
            attrs={"class": "browser-default custom-select form-control"}
        ),
        label="Student",
    )

    relation_ship = forms.CharField(
        widget=forms.Select(
            choices=RELATION_SHIP,
            attrs={
                "class": "browser-default custom-select form-control",
            },
        ),
    )

    password1 = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "password",
                "class": "form-control",
            }
        ),
        label="Password",
    )

    password2 = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "type": "password",
                "class": "form-control",
            }
        ),
        label="Password Confirmation",
    )

    # def validate_email(self):
    #     email = self.cleaned_data['email']
    #     if User.objects.filter(email__iexact=email, is_active=True).exists():
    #         raise forms.ValidationError("Email has taken, try another email address. ")

    class Meta(UserCreationForm.Meta):
        model = User

    @transaction.atomic()
    def save(self):
        user = super().save(commit=False)
        user.is_parent = True
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        user.address = self.cleaned_data.get("address")
        user.phone = self.cleaned_data.get("phone")
        user.email = self.cleaned_data.get("email")
        user.save()
        parent = Parent.objects.create(
            user=user,
            student=self.cleaned_data.get("student"),
            relation_ship=self.cleaned_data.get("relation_ship"),
        )
        parent.save()
        return user


class RegistrarAddForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    phone = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(choices=GENDERS, widget=forms.Select(attrs={"class": "form-select"}))

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "address", "gender"]

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)

        # Set registrar flag
        user.is_registrar = True

        # Generate credentials
        username = f"reg{random.randint(1000, 9999)}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        user.username = username
        user.set_password(password)

        if commit:
            user.save()

            # Save generated values to the form instance for access in views
            self.generated_username = username
            self.generated_password = password

            # Send email
            subject = "Registrar Account Created"
            email_body = render_to_string("accounts/email/new_registrar_account_confirmation.html", {
                "user": user,
                "password": password,
            })

            email = EmailMessage(subject, email_body, settings.EMAIL_FROM_ADDRESS, [user.email])
            email.content_subtype = "html"
            email.send(fail_silently=True)

        return user

class RegistrarModulePermissionForm(forms.ModelForm):
    module_name = forms.ChoiceField(choices=REGISTRAR_MODULES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = RegistrarModulePermission
        fields = ['registrar', 'module_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['registrar'].queryset = User.objects.filter(is_registrar=True)
        self.fields['registrar'].widget.attrs.update({'class': 'form-select'})


class AssignModuleForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_superuser=False).order_by("username"),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Select User'
    )
    modules = forms.MultipleChoiceField(
        choices=ACTIVE_MODULE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Modules',
        required=False,
    )

class FacultyAdminAddForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(choices=GENDERS, widget=forms.Select(attrs={"class": "form-select"}))
    phone = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    faculty = forms.ModelChoiceField(queryset=Faculty.objects.all(), widget=forms.Select(attrs={"class": "form-select"}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone', 'address', 'faculty']

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)
        username = f"fac{get_random_string(5)}"
        password = get_random_string(length=8)

        user.username = username
        user.set_password(password)
        user.is_faculty_admin = True

        if commit:
            user.save()

            # Save generated for use in view
            self.generated_username = username
            self.generated_password = password

            # Send email with credentials
            subject = "Faculty Admin Account Created"
            email_body = render_to_string("accounts/email/new_faculty_account_confirmation.html", {
                "user": user,
                "password": password,
            })
            email = EmailMessage(subject, email_body, settings.EMAIL_FROM_ADDRESS, [user.email])
            email.content_subtype = "html"
            email.send(fail_silently=True)

        return user
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone', 'address', 'faculty']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generated_password = get_random_string(length=8)
        self.fields['faculty'].queryset = Faculty.objects.all()

    @transaction.atomic()
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = f"fac{get_random_string(5)}"
        user.set_password(self.generated_password)
        user.is_faculty_admin = True
        if commit:
            user.save()
        return user
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone', 'address', 'faculty']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generated_password = get_random_string(length=8)
        self.fields['faculty'].queryset = Faculty.objects.all()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = f"fac{get_random_string(5)}"
        user.set_password(self.generated_password)
        user.is_faculty_admin = True
        if commit:
            user.save()
        return user
    
class FacultyLecturerAddForm(forms.ModelForm):
    gender = forms.ChoiceField(choices=GENDERS, widget=forms.Select(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'gender']

        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }

    @transaction.atomic
    def save(self, faculty, commit=True):
        user = super().save(commit=False)
        user.username = f"lec{User.objects.count() + 1}"
        user.set_password("defaultpass123")  # Or use a random password
        user.is_lecturer = True
        user.faculty = faculty
        if commit:
            user.save()
        return user
    

class FacultyLecturerEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "gender", "phone", "address", "faculty", "picture"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["faculty"].widget = forms.HiddenInput()
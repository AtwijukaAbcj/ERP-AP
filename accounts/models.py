from django.db import models
from django.urls import reverse
from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from PIL import Image
from django.core.validators import FileExtensionValidator
from django.core.files.storage import FileSystemStorage
from django.db import transaction
import os

from core.models import Semester
from course.models import Program
from .identifiers import generate_student_registration_number
from .validators import ASCIIUsernameValidator
from course.models import Faculty

# class Faculty(models.Model):
#     name = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return self.name
    
# LEVEL_COURSE = "Level course"
BACHELOR_DEGREE = _("Bachelor")
MASTER_DEGREE = _("Master")

LEVEL = (
    # (LEVEL_COURSE, "Level course"),
    (BACHELOR_DEGREE, _("Bachelor Degree")),
    (MASTER_DEGREE, _("Master Degree")),
)

FATHER = _("Father")
MOTHER = _("Mother")
BROTHER = _("Brother")
SISTER = _("Sister")
GRAND_MOTHER = _("Grand mother")
GRAND_FATHER = _("Grand father")
OTHER = _("Other")

RELATION_SHIP = (
    (FATHER, _("Father")),
    (MOTHER, _("Mother")),
    (BROTHER, _("Brother")),
    (SISTER, _("Sister")),
    (GRAND_MOTHER, _("Grand mother")),
    (GRAND_FATHER, _("Grand father")),
    (OTHER, _("Other")),
)

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "administrator"
ROLE_FINANCE_MANAGER = "finance_manager"
ROLE_ACCOUNTANT = "accountant"
ROLE_PROCUREMENT_OFFICER = "procurement_officer"
ROLE_PROCUREMENT_MANAGER = "procurement_manager"
ROLE_HEAD_OF_DEPARTMENT = "head_of_department"
ROLE_INTERNAL_AUDITOR = "internal_auditor"
ROLE_PRINCIPAL = "principal"
ROLE_STAFF = "staff"

ROLE_CHOICES = (
    (ROLE_SUPER_ADMIN, _("Super Administrator")),
    (ROLE_ADMIN, _("Administrator")),
    (ROLE_FINANCE_MANAGER, _("Finance Manager")),
    (ROLE_ACCOUNTANT, _("Accountant")),
    (ROLE_PROCUREMENT_OFFICER, _("Procurement Officer")),
    (ROLE_PROCUREMENT_MANAGER, _("Procurement Manager")),
    (ROLE_HEAD_OF_DEPARTMENT, _("Head of Department")),
    (ROLE_INTERNAL_AUDITOR, _("Internal Auditor")),
    (ROLE_PRINCIPAL, _("Principal / Executive Director")),
    (ROLE_STAFF, _("Staff")),
)


class Role(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(
        "Permission",
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


class Permission(models.Model):
    module = models.CharField(max_length=100, blank=True, null=True)
    action = models.CharField(max_length=100, blank=True, null=True)
    code = models.CharField(
        max_length=200,
        unique=True,
        db_column="codename",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        unique_together = [("module", "action")]

    def save(self, *args, **kwargs):
        if self.module and self.action:
            self.code = f"{self.module}.{self.action}"
        super().save(*args, **kwargs)

    @property
    def codename(self):
        return self.code

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission")
        ]
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"

    def __str__(self):
        return f"{self.role.name} -> {self.permission.codename}"


class UserPermission(models.Model):
    GRANT = "grant"
    DENY = "deny"

    EFFECT_CHOICES = [
        (GRANT, "Grant"),
        (DENY, "Deny"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="permission_overrides",
    )
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, default=GRANT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_permission_overrides",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "permission"], name="unique_user_permission_override")
        ]

    def __str__(self):
        return f"{self.user.get_full_name} [{self.effect}] {self.permission.code}"


class CustomUserManager(UserManager):
    def search(self, query=None):
        queryset = self.get_queryset()
        if query is not None:
            or_lookup = (
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
            queryset = queryset.filter(
                or_lookup
            ).distinct()  # distinct() is often necessary with Q lookups
        return queryset

    def get_student_count(self):
        return self.model.objects.filter(is_student=True).count()

    def get_lecturer_count(self):
        return self.model.objects.filter(is_lecturer=True).count()

    def get_superuser_count(self):
        return self.model.objects.filter(is_superuser=True).count()


GENDERS = ((_("M"), _("Male")), (_("F"), _("Female")))


class User(AbstractUser):
    last_activity = models.DateTimeField(blank=True, null=True, db_index=True)
    is_student = models.BooleanField(default=False)
    is_lecturer = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    is_dep_head = models.BooleanField(default=False)
    is_finance = models.BooleanField(default=False)
    is_registrar = models.BooleanField(default=False)
    is_temp_field = models.BooleanField(default=False)
    is_faculty_admin = models.BooleanField(default=False)
    is_finance_manager = models.BooleanField(default=False)
    is_accountant = models.BooleanField(default=False)
    is_procurement_officer = models.BooleanField(default=False)
    is_procurement_manager = models.BooleanField(default=False)
    is_internal_auditor = models.BooleanField(default=False)
    is_principal = models.BooleanField(default=False)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    faculty = models.ForeignKey(Faculty, null=True, blank=True, on_delete=models.SET_NULL)
    gender = models.CharField(max_length=1, choices=GENDERS, blank=True, null=True)
    phone = models.CharField(max_length=60, blank=True, null=True)
    address = models.CharField(max_length=60, blank=True, null=True)
    picture = models.ImageField(
        upload_to="profile_pictures/%y/%m/%d/", default="default.png", null=True
    )
    email = models.EmailField(blank=True, null=True)

    username_validator = ASCIIUsernameValidator()

    objects = CustomUserManager()

    class Meta:
        ordering = ("-date_joined",)

    @property
    def get_full_name(self):
        full_name = self.username
        if self.first_name and self.last_name:
            full_name = self.first_name + " " + self.last_name
        return full_name

    def __str__(self):
        return "{} ({})".format(self.username, self.get_full_name)

    @property
    def get_user_role(self):
        role_names = list(self.roles.order_by("name").values_list("name", flat=True))
        if self.role_id and self.role.name not in role_names:
            role_names.append(self.role.name)

        account_types = (
            (self.is_superuser, _("Super Administrator")),
            (self.is_finance_manager, _("Finance Manager")),
            (self.is_accountant, _("Accountant")),
            (self.is_procurement_manager, _("Procurement Manager")),
            (self.is_procurement_officer, _("Procurement Officer")),
            (self.is_internal_auditor, _("Internal Auditor")),
            (self.is_principal, _("Principal / Executive Director")),
            (self.is_registrar, _("Academic Registrar")),
            (self.is_dep_head, _("Head of Department")),
            (self.is_faculty_admin, _("Faculty Admin")),
            (self.is_finance, _("Finance")),
            (self.is_student, _("Student")),
            (self.is_lecturer, _("Lecturer")),
            (self.is_parent, _("Parent")),
        )
        role_names.extend(str(label) for enabled, label in account_types if enabled)
        return " / ".join(dict.fromkeys(role_names)) if role_names else _("User")

    @property
    def module_permissions(self):
        if self.is_superuser:
            return [choice[0] for choice in ACTIVE_MODULE_CHOICES]
        return list(self.get_effective_permissions())

    def has_role(self, role_slug):
        if not self.is_authenticated or not self.is_active:
            return False
        if self.role_id and self.role.slug == role_slug:
            return True
        return self.roles.filter(slug=role_slug).exists()

    def has_permission(self, permission_code):
        if not self.is_authenticated or not self.is_active:
            return False

        if self.is_superuser:
            return True

        override = self.permission_overrides.filter(
            permission__code=permission_code
        ).values_list("effect", flat=True).first()

        if override == UserPermission.DENY:
            return False

        if override == UserPermission.GRANT:
            return True

        return permission_code in self.get_effective_permissions()

    def get_effective_permissions(self):
        if not self.is_authenticated or not self.is_active:
            return set()

        if self.is_superuser:
            return set(Permission.objects.values_list("code", flat=True))

        effective = set()
        if self.role_id:
            effective.update(
                code
                for code in self.role.permissions.values_list("code", flat=True)
                if code
            )
        effective.update(
            code
            for code in self.roles.values_list("permissions__code", flat=True)
            if code
        )

        module_permissions = set(self.general_module_permissions.values_list('module_name', flat=True))
        finance_permissions = set(self.finance_permissions.values_list('module_name', flat=True))
        registrar_permissions = set(self.registrarmodulepermission_set.values_list('module_name', flat=True))

        effective.update(module_permissions)
        effective.update(finance_permissions)
        effective.update(registrar_permissions)

        overrides = self.permission_overrides.select_related("permission").all()
        for override in overrides:
            if override.effect == UserPermission.DENY:
                effective.discard(override.permission.code)
            elif override.effect == UserPermission.GRANT:
                effective.add(override.permission.code)

        return effective

    def can_access_module(self, module_name):
        if not self.is_authenticated or not self.is_active:
            return False

        if self.is_superuser:
            return True

        effective_permissions = self.get_effective_permissions()
        module_prefix = f"{module_name}."
        legacy_prefix = f"{module_name}_"
        module_names = {module_name}
        legacy_prefixes = {legacy_prefix}
        if module_name.endswith("s"):
            module_names.add(module_name[:-1])
            legacy_prefixes.add(f"{module_name[:-1]}_")

        if module_name == "finance":
            finance_codes = {
                "finance",
                "finance.fee_category.add",
                "finance.fee_category.edit",
                "finance.fee_category.delete",
                "manage_fee_categories",
                "create_invoice",
                "manage_invoices",
                "view_student_invoices",
                "staff_category_list",
                "staff_list",
                "payroll_list",
                "expense_category_list",
                "expense_list",
                "petty_cash_list",
                "accounts_payable_list",
                "accounts_receivable_list",
                "budget_list",
                "cash_book_list",
                "bank_reconciliation_list",
                "ledger_account_list",
                "general_ledger_list",
                "payment_voucher_list",
                "finance_reports",
            }
            return bool(effective_permissions.intersection(finance_codes))

        return any(
            isinstance(code, str)
            and (
                code in module_names
                or code.startswith(module_prefix)
                or any(code.startswith(prefix) for prefix in legacy_prefixes)
            )
            for code in effective_permissions
        )

    def has_module_permission(self, module_name):
        # Deprecated transitional helper. Use has_permission() or can_access_module() instead.
        return self.can_access_module(module_name)

    def get_picture(self):
        try:
            return self.picture.url
        except:
            no_picture = settings.MEDIA_URL + "default.png"
            return no_picture

    def get_absolute_url(self):
        return reverse("profile_single", kwargs={"user_id": self.id})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            img = Image.open(self.picture.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.picture.path)
        except:
            pass

    def delete(self, *args, **kwargs):
        if self.picture.url != settings.MEDIA_URL + "default.png":
            self.picture.delete()
        super().delete(*args, **kwargs)
    

class StudentManager(models.Manager):
    def search(self, query=None):
        qs = self.get_queryset()
        if query is not None:
            or_lookup = (
                Q(level__icontains=query)
                | Q(program__title__icontains=query)
                | Q(year__icontains=query)
                | Q(semester__semester__icontains=query)
            )
            qs = qs.filter(
                or_lookup
            ).distinct()  # distinct() is often necessary with Q lookups
        return qs


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        ON_LEAVE = "on_leave", _("On leave")
        SUSPENDED = "suspended", _("Suspended")
        GRADUATED = "graduated", _("Graduated")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    student = models.OneToOneField(User, on_delete=models.CASCADE)
    registration_number = models.CharField(max_length=60, unique=True, null=True, blank=True)
    level = models.CharField(max_length=50, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, null=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    semester = models.ForeignKey(Semester, null=True, blank=True, on_delete=models.SET_NULL)
    date_of_birth = models.DateField(null=True, blank=True)
    cohort = models.CharField(max_length=100, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    next_of_kin_name = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=60, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    objects = StudentManager()

    class Meta:
        ordering = ("-student__date_joined",)

    def save(self, *args, **kwargs):
        if self.registration_number:
            return super().save(*args, **kwargs)

        using = kwargs.get("using")
        with transaction.atomic(using=using):
            if self.pk is None:
                super().save(*args, **kwargs)
                self.registration_number = generate_student_registration_number(self)
                return super().save(
                    update_fields=("registration_number",),
                    using=using,
                )

            self.registration_number = generate_student_registration_number(self)
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"registration_number"}
            return super().save(*args, **kwargs)

    def __str__(self):
        return self.student.get_full_name

    @classmethod
    def get_gender_count(cls):
        males_count = Student.objects.filter(student__gender="M").count()
        females_count = Student.objects.filter(student__gender="F").count()
        return {"M": males_count, "F": females_count}

    def get_absolute_url(self):
        return reverse("profile_single", kwargs={"user_id": self.id})

    def delete(self, *args, **kwargs):
        self.student.delete()
        super().delete(*args, **kwargs)


class PrivateStudentDocumentStorage(FileSystemStorage):
    def url(self, name):
        raise ValueError(
            "Student documents are available only through authenticated downloads."
        )


def student_document_storage():
    return PrivateStudentDocumentStorage(
        location=os.path.join(settings.BASE_DIR, "private_student_documents"),
    )


class StudentDocument(models.Model):
    class Category(models.TextChoices):
        IDENTIFICATION = "identification", _("Identification")
        ACADEMIC = "academic", _("Academic record")
        MEDICAL = "medical", _("Medical")
        FINANCIAL = "financial", _("Financial")
        OTHER = "other", _("Other")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    category = models.CharField(max_length=30, choices=Category.choices)
    title = models.CharField(max_length=200)
    file = models.FileField(
        upload_to="student_documents/%Y/%m/",
        storage=student_document_storage,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"])],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_student_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"{self.student.registration_number}: {self.title}"


class StudentStatusHistory(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=20, choices=Student.Status.choices)
    to_status = models.CharField(max_length=20, choices=Student.Status.choices)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)

    def __str__(self):
        return (
            f"{self.student.registration_number}: "
            f"{self.from_status} -> {self.to_status}"
        )


REGISTRAR_MODULES = [
    ('add_results', 'Add Results'),
    ('edit_results', 'Edit Results'),
    ('view_transcripts', 'View Transcripts'),
    ('manage_clearance', 'Manage Clearance'),
]

class RegistrarModulePermission(models.Model):
    registrar = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_registrar': True})
    module_name = models.CharField(max_length=50, choices=REGISTRAR_MODULES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['registrar', 'module_name'], name='unique_registrar_module')
        ]

    def __str__(self):
        return f"{self.registrar.get_full_name} - {self.module_name}"


class Parent(models.Model):
    """
    Connect student with their parent, parents can
    only view their connected students information
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student = models.OneToOneField(Student, null=True, on_delete=models.SET_NULL)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=60, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # What is the relationship between the student and
    # the parent (i.e. father, mother, brother, sister)
    relation_ship = models.TextField(choices=RELATION_SHIP, blank=True)

    class Meta:
        ordering = ("-user__date_joined",)

    def __str__(self):
        return self.user.username


class DepartmentHead(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(Program, on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ("-user__date_joined",)

    def __str__(self):
        return "{}".format(self.user)

FINANCE_MODULES = [
    ('manage_fee_categories', 'Manage Fee Categories'),
    ('create_invoice', 'Create Invoice'),
    ('manage_invoices', 'Manage Invoices'),
    ('view_student_invoices', 'View Student Invoices'),
]

class FinanceModulePermission(models.Model):
    staff = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'is_finance': True},
        related_name='finance_permissions'  # ✅ to fix reverse accessor clash
    )
    module_name = models.CharField(max_length=50, choices=FINANCE_MODULES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['staff', 'module_name'], name='unique_staff_module')
        ]

    def __str__(self):
        return f"{self.staff.get_full_name} - {self.module_name}"



MODULE_CHOICES = [
    # Admin-related
    ('admin_panel', 'Admin Panel'),

    # User Management
    ('lecturers', 'Lecturers'),
    ('students', 'Students'),

    # Program Management
    ('programs', 'Programs'),
    ('program_add', 'Add Program'),
    ('program_edit', 'Edit Program'),
    ('program_delete', 'Delete Program'),

    # Course Management
    ('courses', 'Courses'),
    ('course_add', 'Add Course'),
    ('course_edit', 'Edit Course'),
    ('course_delete', 'Delete Course'),
    ('course_detail', 'View Course'),
    ('course_file_upload', 'Upload Course File'),
    ('course_file_edit', 'Edit Course File'),
    ('course_file_delete', 'Delete Course File'),
    ('course_video_upload', 'Upload Course Video'),
    ('course_video_edit', 'Edit Course Video'),
    ('course_video_delete', 'Delete Course Video'),

    # Course Allocation
    ('course_allocation', 'Course Allocation'),
    ('course_allocation_edit', 'Edit Course Allocation'),
    ('course_allocation_deallocate', 'Deallocate Course'),

    # Procurement
    ('procurement_dashboard', 'Procurement Dashboard'),
    ('procurement_suppliers', 'View Suppliers'),
    ('procurement_suppliers_add', 'Add Supplier'),
    ('procurement_suppliers_edit', 'Edit Supplier'),
    ('procurement_suppliers_delete', 'Delete Supplier'),
    ('procurement_supplier_categories', 'View Supplier Categories'),
    ('procurement_supplier_categories_add', 'Add Supplier Category'),
    ('procurement_supplier_categories_edit', 'Edit Supplier Category'),
    ('procurement_supplier_categories_delete', 'Delete Supplier Category'),
    ('procurement_plans', 'View Procurement Plans'),
    ('procurement_plans_add', 'Add Procurement Plan'),
    ('procurement_plans_edit', 'Edit Procurement Plan'),
    ('procurement_plans_delete', 'Delete Procurement Plan'),
    ('procurement_requisitions', 'View Purchase Requisitions'),
    ('procurement_requisitions_add', 'Add Purchase Requisition'),
    ('procurement_requisitions_edit', 'Edit Purchase Requisition'),
    ('procurement_requisitions_delete', 'Delete Purchase Requisition'),
    ('procurement_requisitions_export', 'Export Purchase Requisitions'),
    ('procurement_orders', 'View Purchase Orders'),
    ('procurement_orders_add', 'Add Purchase Order'),
    ('procurement_orders_edit', 'Edit Purchase Order'),
    ('procurement_orders_delete', 'Delete Purchase Order'),
    ('procurement_orders_export', 'Export Purchase Orders'),

    # Session & Semester
    ('sessions', 'Sessions'),
    ('semesters', 'Semesters'),

    # Session & Semester
    ('sessions', 'Sessions'),
    ('semesters', 'Semesters'),

    # Faculties
    ('faculties', 'Manage Faculties'),
    ('faculty_add', 'Add Faculty'),
    ('faculty_edit', 'Edit Faculty'),
    ('faculty_delete', 'Delete Faculty'),

    # Course Registration (Student)
    ('course_registration', 'Course Registration'),
    ('drop_course', 'Drop Course'),

    # Assessments and Quizzes
    ('quiz_progress', 'Quiz Progress'),
    ('quiz_marking', 'Quiz Marking'),
    ('quiz_attempts', 'View Quiz Attempts'),
    ('view_sittings', 'Completed Quizzes'),

    # Student Results
    ('results_grading', 'Results Grading'),
    ('assessment_results', 'Assessment Results'),
    ('add_results', 'Add Results'),
    ('edit_results', 'Edit Results'),
    ('view_transcripts', 'View Transcripts'),

    # GPA & CGPA
    ('gpa_view', 'GPA View'),
    ('cgpa_view', 'CGPA View'),

    # News and Events
    ('news_events', 'News and Events'),

    # Course File Management
    ('upload_course_file', 'Upload Course File'),
    ('edit_course_file', 'Edit Course File'),
    ('delete_course_file', 'Delete Course File'),

    # Course Video Management
    ('upload_course_video', 'Upload Course Video'),
    ('edit_course_video', 'Edit Course Video'),
    ('delete_course_video', 'Delete Course Video'),

    # Miscellaneous
    ('user_courses', 'My Courses'),
]

ACTIVE_MODULE_CHOICES = [
    ('admin_panel', 'Admin Panel'),
    ('lecturers', 'Lecturers'),
    ('students', 'Students'),
    ('programs', 'Programs'),
    ('program_add', 'Add Program'),
    ('program_edit', 'Edit Program'),
    ('program_delete', 'Delete Program'),
    ('course', 'Courses'),
    ('course_add', 'Add Course'),
    ('course_edit', 'Edit Course'),
    ('course_delete', 'Delete Course'),
    ('course_detail', 'View Course'),
    ('course_file_upload', 'Upload Course File'),
    ('course_file_edit', 'Edit Course File'),
    ('course_file_delete', 'Delete Course File'),
    ('course_video_upload', 'Upload Course Video'),
    ('course_video_edit', 'Edit Course Video'),
    ('course_video_delete', 'Delete Course Video'),
    ('course_allocation', 'Course Allocation'),
    ('course_allocation_edit', 'Edit Course Allocation'),
    ('course_allocation_deallocate', 'Deallocate Course'),
    ('course_registration', 'Course Registration'),
    ('drop_course', 'Drop Course'),
    ('user_courses', 'My Courses'),
    ('quiz_progress', 'Quiz Progress'),
    ('quiz_marking', 'Quiz Marking'),
    ('quiz_attempts', 'View Quiz Attempts'),
    ('view_sittings', 'Completed Quizzes'),
    ('results_grading', 'Results Grading'),
    ('assessment_results', 'Assessment Results'),
    ('add_results', 'Add Results'),
    ('edit_results', 'Edit Results'),
    ('view_transcripts', 'View Transcripts'),
    ('gpa_view', 'GPA View'),
    ('cgpa_view', 'CGPA View'),
    ('sessions', 'Sessions'),
    ('semesters', 'Semesters'),
    ('faculties', 'Manage Faculties'),
    ('faculty_add', 'Add Faculty'),
    ('faculty_edit', 'Edit Faculty'),
    ('faculty_delete', 'Delete Faculty'),
    ('admissions', 'Admissions'),
    ('admissions.view_applications', 'View Applications'),
    ('admissions.manage_applications', 'Manage Applications'),
    ('admissions.review_applications', 'Review Applications'),
    ('students.view_students', 'View Student Records'),
    ('students.manage_students', 'Manage Student Records'),
    ('students.edit_students', 'Edit Student Records'),
    ('students.delete_students', 'Delete Student Records'),
    ('students.manage_documents', 'Manage Student Documents'),
    ('students.view_documents', 'View Student Documents'),
    ('students.export_students', 'Export Student Records'),
    ('clinical', 'Clinical Placements'),
    ('clinical.view_placements', 'View Clinical Placements'),
    ('clinical.manage_placements', 'Manage Clinical Placements'),
    ('clinical.verify_log_entries', 'Review Clinical Log Entries'),
    ('clinical.approve_placements', 'Approve Clinical Placements'),
    ('admissions.link_students', 'Link Admitted Students'),
    ('assignments', 'Assignments'),
    ('assignments.view', 'View Assignments'),
    ('assignments.manage', 'Manage Assignments'),
    ('quizzes', 'Quizzes'),
    ('quizzes.view', 'View Quizzes'),
    ('quizzes.manage', 'Manage Quizzes'),
    ('quizzes.mark', 'Mark Quizzes'),
    ('results', 'Results'),
    ('results.view', 'View Results'),
    ('results.manage', 'Manage Results'),
    ('results.publish', 'Publish Results'),
    ('voting', 'Voting'),
    ('voting.view', 'View Elections'),
    ('voting.manage', 'Manage Elections'),
    ('audit', 'Audit Logs'),
    ('audit.view', 'View Audit Logs'),
    ('reports', 'Reports'),
    ('reports.view', 'View Reports'),
    ('finance', 'Finance'),
    
    # Finance
    ('manage_fee_categories', 'Manage Fee Categories'),
    ('create_invoice', 'Create Invoice'),
    ('manage_invoices', 'Manage Invoices'),
    ('view_student_invoices', 'View Student Invoices'),
    ('staff_category_list', 'Staff Categories'),
    ('staff_list', 'Staff Members'),
    ('payroll_list', 'Payroll'),
    ('expense_category_list', 'Expense Categories'),
    ('expense_list', 'Expenses'),
    ('petty_cash_list', 'Petty Cash'),
    ('accounts_payable_list', 'Accounts Payable'),
    ('accounts_receivable_list', 'Accounts Receivable'),
    ('budget_list', 'Budgets'),
    ('cash_book_list', 'Cash Book'),
    ('bank_reconciliation_list', 'Bank Reconciliation'),
    ('ledger_account_list', 'Ledger Accounts'),
    ('general_ledger_list', 'General Ledger'),
    ('payment_voucher_list', 'Payment Vouchers'),
    ('finance_reports', 'Finance Reports'),

    # Procurement
    ('procurement', 'Procurement'),
    ('procurement_dashboard', 'Procurement Dashboard'),
    ('procurement_suppliers', 'View Suppliers'),
    ('procurement_suppliers_add', 'Add Supplier'),
    ('procurement_suppliers_edit', 'Edit Supplier'),
    ('procurement_suppliers_delete', 'Delete Supplier'),
    ('procurement_supplier_categories', 'View Supplier Categories'),
    ('procurement_supplier_categories_add', 'Add Supplier Category'),
    ('procurement_supplier_categories_edit', 'Edit Supplier Category'),
    ('procurement_supplier_categories_delete', 'Delete Supplier Category'),
    ('procurement_plans', 'View Procurement Plans'),
    ('procurement_plans_add', 'Add Procurement Plan'),
    ('procurement_plans_edit', 'Edit Procurement Plan'),
    ('procurement_plans_delete', 'Delete Procurement Plan'),
    ('procurement_plans_approve', 'Approve Procurement Plan'),
    ('procurement_departments', 'View Procurement Departments'),
    ('procurement_departments_add', 'Manage Procurement Departments'),
    ('procurement_departments_edit', 'Edit Procurement Departments'),
    ('procurement_departments_delete', 'Delete Procurement Departments'),
    ('procurement_statuses', 'Manage Procurement Statuses'),
    ('procurement_workflows', 'Manage Procurement Workflows'),
    ('procurement_requisitions', 'View Purchase Requisitions'),
    ('procurement_requisitions_add', 'Add Purchase Requisition'),
    ('procurement_requisitions_edit', 'Edit Purchase Requisition'),
    ('procurement_requisitions_delete', 'Delete Purchase Requisition'),
    ('procurement_requisitions_export', 'Export Purchase Requisitions'),
    ('procurement_requisitions_approve', 'Approve Purchase Requisitions'),
    ('procurement_orders', 'View Purchase Orders'),
    ('procurement_orders_add', 'Add Purchase Order'),
    ('procurement_orders_edit', 'Edit Purchase Order'),
    ('procurement_orders_delete', 'Delete Purchase Order'),
    ('procurement_orders_export', 'Export Purchase Orders'),
    ('procurement_orders_approve', 'Approve Purchase Orders'),
    ('procurement_quotations', 'View Supplier Quotations'),
    ('procurement_quotations_add', 'Add Supplier Quotations'),
    ('procurement_quotations_edit', 'Manage Supplier Quotations'),
]


class ModulePermission(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='general_module_permissions'
    )
    module_name = models.CharField(max_length=100, choices=ACTIVE_MODULE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'module_name'], name='unique_user_module')
        ]

    def __str__(self):
        return f"{self.user.get_full_name} - {self.module_name}"

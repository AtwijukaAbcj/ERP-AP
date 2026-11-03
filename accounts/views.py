from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template, render_to_string
from django.utils.decorators import method_decorator
from django.views.generic import CreateView
from django_filters.views import FilterView

from accounts.decorators import (
    admin_required,
    lecturer_directory_required,
    student_management_required,
    user_has_student_management_permission,
)
from accounts.filters import LecturerFilter, StudentFilter
from accounts.forms import (
    ParentAddForm,
    ProfileUpdateForm,
    ProgramUpdateForm,
    RoleForm,
    PermissionForm,
    RolePermissionForm,
    UserPermissionForm,
    UserAddForm,
    UserRolesForm,
    StaffAddForm,
    StudentAddForm,
    StudentDocumentForm,
    StudentStatusForm,
)
from accounts.models import (
    Parent,
    Role,
    Student,
    StudentDocument,
    StudentStatusHistory,
    User,
    Permission,
    RolePermission,
    UserPermission,
)
from core.models import Semester, Session, SiteSettings
from core.pdf_utils import pdf_link_callback
from accounts.forms import FinanceAddForm
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from accounts.forms import StudentEditForm
from accounts.student_services import transition_student_status
from audit.utils import log_activity
from django.views.decorators.http import require_POST
import random
import string
from .forms import RegistrarAddForm
import csv
from reportlab.pdfgen import canvas
# ########################################################
# Utility Functions
# ########################################################

from django.shortcuts import render, redirect
from .forms import RegistrarModulePermissionForm
from .models import RegistrarModulePermission
from .models import FinanceModulePermission
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from accounts.models import User, FinanceModulePermission
from django.contrib import messages

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import AssignModuleForm
from .models import ModulePermission
from .forms import FacultyAdminAddForm

from django.core.mail import EmailMessage
from accounts.forms import StudentEditForm  
from django import forms

from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def custom_logout_view(request):
    """Custom logout view that handles both GET and POST requests for Django 5.0+ compatibility."""
    logout(request)
    return redirect('/')


def generate_code():
    return ''.join(random.choices(string.digits, k=6))


def send_code_to_email(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            if not user.email:
                messages.error(request, "This account does not have an email address configured.")
                return render(request, "registration/login.html", {"debug_code": None})

            # Generate random code
            code = generate_code()

            # Save code in session with an expiration time
            request.session["auth_code"] = code
            expiry_time = timezone.now() + timedelta(minutes=10)
            request.session["auth_code_expiry"] = expiry_time.isoformat()
            request.session["username"] = username

            # Send email with the code
            email_subject = "Your Login Verification Code"
            email_body = f"Your verification code is: {code}. It will expire in 10 minutes."
            email = EmailMessage(
                email_subject,
                email_body,
                settings.EMAIL_FROM_ADDRESS,
                [user.email],
            )
            debug_code = None
            try:
                email.send(fail_silently=False)
            except Exception:
                messages.warning(request, "Verification email could not be delivered. Please check email settings.")
                if settings.DEBUG:
                    debug_code = code

            if debug_code:
                messages.info(request, f"Debug verification code: {debug_code}")
            else:
                messages.success(request, "A verification code has been sent to your email.")

            return redirect("verify_code")

        messages.error(request, "Invalid username or password.")
        return render(request, "registration/login.html", {"debug_code": None})

    return render(request, "registration/login.html", {"debug_code": None})



def verify_code(request):
    if request.method == "POST":
        entered_code = request.POST['verification_code']

        # Get code and expiry time from the session
        stored_code = request.session.get('auth_code')
        code_expiry = request.session.get('auth_code_expiry')

        if stored_code and code_expiry:
            code_expiry = parse_datetime(code_expiry)
            if code_expiry and timezone.is_naive(code_expiry):
                code_expiry = timezone.make_aware(code_expiry, timezone=timezone.utc)

            if code_expiry and timezone.now() < code_expiry:
                if entered_code == stored_code:
                    username = request.session.get('username')
                    try:
                        user = User.objects.get(username=username)
                        login(request, user)  # Log the user in
                        return redirect('home')  # Redirect to the homepage after successful login
                    except User.DoesNotExist:
                        messages.error(request, "User not found. Please try again.")
                        return redirect('login')
                else:
                    messages.error(request, "Invalid code. Please try again.")
            else:
                messages.error(request, "The code has expired. Please request a new one.")
        else:
            messages.error(request, "Verification code is invalid or expired.")

    return render(request, 'registration/verify_code.html')

@login_required
@admin_required
def assign_modules_view(request):
    search_query = request.GET.get('user_search', '').strip()

    if request.method == "POST":
        form = AssignModuleForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            selected_modules = set(form.cleaned_data['modules'])
            current_modules = set(
                ModulePermission.objects.filter(user=user).values_list(
                    "module_name", flat=True
                )
            )
            with transaction.atomic():
                ModulePermission.objects.filter(user=user).exclude(
                    module_name__in=selected_modules
                ).delete()
                ModulePermission.objects.bulk_create(
                    [
                        ModulePermission(user=user, module_name=module)
                        for module in selected_modules - current_modules
                    ]
                )
            log_activity(
                request.user,
                "rbac.module_access.updated",
                f"Updated module access for {user.username}.",
                request=request,
                instance=user,
                before={"modules": sorted(current_modules)},
                after={"modules": sorted(selected_modules)},
            )

            messages.success(request, "Modules assigned successfully.")
            return redirect('assign_modules')
    else:
        initial = {}
        selected_user_id = request.GET.get("user_id")
        if selected_user_id:
            selected_user = get_object_or_404(
                User.objects.filter(is_superuser=False),
                pk=selected_user_id,
            )
            initial = {
                "user": selected_user,
                "modules": ModulePermission.objects.filter(
                    user=selected_user
                ).values_list("module_name", flat=True),
            }
        form = AssignModuleForm(initial=initial)

    permissions = ModulePermission.objects.select_related('user')
    if search_query:
        permissions = permissions.filter(
            Q(user__username__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    permissions = permissions.order_by('user__first_name', 'user__last_name', 'user__username')

    return render(request, "accounts/assign_modules.html", {
        "form": form,
        "permissions": permissions,
        "search_query": search_query,
    })


@login_required
@admin_required
@require_POST
def revoke_module_permission(request, perm_id):
    perm = get_object_or_404(ModulePermission, id=perm_id)
    user = perm.user
    module_name = perm.module_name
    perm.delete()
    log_activity(
        request.user,
        "rbac.module_access.revoked",
        f"Revoked {module_name} access from {user.username}.",
        request=request,
        instance=user,
        before={"module": module_name},
    )
    messages.success(request, "Module access revoked.")
    return redirect('assign_modules')


def render_to_pdf(template_name, context):
    """Render a given template to PDF format."""
    from xhtml2pdf import pisa

    response = HttpResponse(content_type="application/pdf")
    profile_id = context["user"].pk
    response["Content-Disposition"] = (
        f'attachment; filename="profile_{profile_id}.pdf"'
    )
    context["site_settings"] = SiteSettings.get_settings()
    template = render_to_string(template_name, context)
    pdf = pisa.CreatePDF(
        template,
        dest=response,
        link_callback=pdf_link_callback,
    )
    if pdf.err:
        return HttpResponse("The profile PDF could not be generated.", status=500)
    return response


# ########################################################
# Authentication and Registration
# ########################################################

def validate_username(request):
    username = request.GET.get("username", None)
    data = {"is_taken": User.objects.filter(username__iexact=username).exists()}
    return JsonResponse(data)


def register(request):
    if request.method == "POST":
        form = StudentAddForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully.")
            return redirect("login")
        messages.error(
            request, "Something is not correct, please fill all fields correctly."
        )
    else:
        form = StudentAddForm()
    return render(request, "registration/register.html", {"form": form})


# ########################################################
# Profile Views
# ########################################################


@login_required
def profile(request):
    """Show profile of the current user."""
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(
        is_current_semester=True, session=current_session
    ).first()

    context = {
        "title": request.user.get_full_name,
        "current_session": current_session,
        "current_semester": current_semester,
    }

    if request.user.is_lecturer:
        context["user_type"] = "Lecturer"
    elif request.user.is_student:
        student = get_object_or_404(Student, student__pk=request.user.id)
        parent = Parent.objects.filter(student=student).first()
        context.update(
            {
                "parent": parent,
                "level": student.level,
            }
        )
    else:
        context["user_type"] = "Staff"

    return render(request, "accounts/profile.html", context)


@login_required
def account_landing(request):
    user = request.user
    if user.is_superuser:
        return redirect("dashboard")
    if user.is_student:
        return redirect("student_list")
    if user.is_registrar:
        return redirect("student_list")
    if user.is_lecturer:
        return redirect("assessment_hub")
    if user.is_finance or user.is_finance_manager or user.is_accountant:
        return redirect("finance:finance_dashboard")
    return redirect("home")


@login_required
@admin_required
def profile_single(request, user_id):
    """Show profile of any selected user."""
    if request.user.id == user_id:
        return redirect("profile")

    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(
        is_current_semester=True, session=current_session
    ).first()
    user = get_object_or_404(User, pk=user_id)

    context = {
        "title": user.get_full_name,
        "user": user,
        "current_session": current_session,
        "current_semester": current_semester,
    }

    form = None
    edit_mode = request.GET.get("edit") == "1"

    if user.is_lecturer:
        context["user_type"] = "Lecturer"
    elif user.is_student:
        student = get_object_or_404(Student, student__pk=user_id)
        context.update(
            {
                "user_type": "Student",
                "student": student,
            }
        )
    else:
        context["user_type"] = "Superuser"

    if edit_mode:
        if user.is_student:
            student = context.get("student")
            if request.method == "POST":
                form = StudentEditForm(request.POST, request.FILES, instance=user, student_instance=student)
                if form.is_valid():
                    form.save()
                    log_activity(
                        request.user,
                        "UPDATE",
                        f"Student record {student.registration_number or student.pk} updated.",
                        request=request,
                        instance=student,
                    )
                    messages.success(request, f"{user.get_full_name}'s profile has been updated.")
                    return redirect("profile_single", user_id=user_id)
            else:
                form = StudentEditForm(instance=user, student_instance=student)
        else:
            if request.method == "POST":
                form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
                if form.is_valid():
                    form.save()
                    messages.success(request, f"{user.get_full_name}'s profile has been updated.")
                    return redirect("profile_single", user_id=user_id)
            else:
                form = ProfileUpdateForm(instance=user)

        context["form"] = form
        context["edit_mode"] = True

    if request.GET.get("download_pdf"):
        return render_to_pdf("pdf/profile_single.html", context)

    return render(request, "accounts/profile_single.html", context)


@login_required
@admin_required
def user_list(request):
    users = User.objects.select_related('role').all().order_by('-date_joined')
    return render(request, "accounts/user_list.html", {"users": users, "title": "Users"})


@login_required
@admin_required
def user_password_reset(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        form = SetPasswordForm(target_user, request.POST)
        if form.is_valid():
            form.save()
            if target_user.pk == request.user.pk:
                update_session_auth_hash(request, target_user)
            log_activity(
                request.user,
                "user.password_reset",
                f"Reset password for user {target_user.username}.",
                request=request,
                instance=target_user,
            )
            messages.success(
                request,
                f"Password for {target_user.get_full_name} has been updated.",
            )
            return redirect("user_list")
    else:
        form = SetPasswordForm(target_user)

    return render(
        request,
        "accounts/user_password_reset.html",
        {
            "form": form,
            "target_user": target_user,
            "title": "Reset User Password",
        },
    )


@login_required
@admin_required
def user_add_view(request):
    if request.method == "POST":
        form = UserAddForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_activity(
                request.user,
                "user.created",
                f"Created user account {user.username}.",
                request=request,
                instance=user,
                after={"username": user.username, "role": None},
            )
            messages.success(request, "User created successfully.")
            return redirect("user_list")
    else:
        form = UserAddForm()
    return render(request, "accounts/user_form.html", {"form": form, "title": "Create User"})


@login_required
@admin_required
def user_roles_view(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    if request.method == "POST":
        form = UserRolesForm(request.POST, instance=user)
        if form.is_valid():
            previous_roles = sorted(user.roles.values_list("name", flat=True))
            if user.role_id and user.role.name not in previous_roles:
                previous_roles.append(user.role.name)
            with transaction.atomic():
                form.save()
            updated_roles = sorted(user.roles.values_list("name", flat=True))
            log_activity(
                request.user,
                "rbac.user_roles.updated",
                f"Updated permission roles for {user.username}.",
                request=request,
                instance=user,
                before={"roles": previous_roles},
                after={"roles": updated_roles},
            )
            messages.success(request, "User roles updated successfully.")
            return redirect("user_list")
    else:
        form = UserRolesForm(instance=user)

    return render(
        request,
        "accounts/user_roles_form.html",
        {"form": form, "target_user": user, "title": "Assign User Roles"},
    )


@login_required
@admin_required
def role_list_view(request):
    roles = Role.objects.all().order_by("name")
    return render(request, "accounts/role_list.html", {"roles": roles, "title": "Roles"})


@login_required
@admin_required
def role_add_view(request):
    if request.method == "POST":
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save()
            log_activity(
                request.user,
                "rbac.role.created",
                f"Created role {role.slug}.",
                request=request,
                instance=role,
                after={"name": role.name, "slug": role.slug},
            )
            messages.success(request, "Role created successfully.")
            return redirect("role_list")
    else:
        form = RoleForm()
    return render(request, "accounts/role_form.html", {"form": form, "title": "Create Role"})


@login_required
@admin_required
def role_edit_view(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if request.method == "POST":
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            before = {"name": role.name, "slug": role.slug}
            role = form.save()
            log_activity(
                request.user,
                "rbac.role.updated",
                f"Updated role {role.slug}.",
                request=request,
                instance=role,
                before=before,
                after={"name": role.name, "slug": role.slug},
            )
            messages.success(request, "Role updated successfully.")
            return redirect("role_list")
    else:
        form = RoleForm(instance=role)
    return render(request, "accounts/role_form.html", {"form": form, "title": "Edit Role"})


@login_required
@admin_required
@require_POST
def role_delete_view(request, pk):
    role = get_object_or_404(Role, pk=pk)
    before = {"name": role.name, "slug": role.slug}
    log_activity(
        request.user,
        "rbac.role.deleted",
        f"Deleted role {role.slug}.",
        request=request,
        instance=role,
        before=before,
    )
    role.delete()
    messages.success(request, "Role deleted successfully.")
    return redirect("role_list")


@login_required
@admin_required
def permission_list_view(request):
    permissions = Permission.objects.all().order_by("code")
    return render(request, "accounts/permission_list.html", {"permissions": permissions, "title": "Permissions"})


@login_required
@admin_required
def permission_add_view(request):
    if request.method == "POST":
        form = PermissionForm(request.POST)
        if form.is_valid():
            permission = form.save()
            log_activity(
                request.user,
                "rbac.permission.created",
                f"Created permission {permission.code}.",
                request=request,
                instance=permission,
                after={"name": permission.name, "code": permission.code},
            )
            messages.success(request, "Permission created successfully.")
            return redirect("permission_list")
    else:
        form = PermissionForm()
    return render(request, "accounts/permission_form.html", {"form": form, "title": "Create Permission"})


@login_required
@admin_required
def permission_edit_view(request, pk):
    permission = get_object_or_404(Permission, pk=pk)
    if request.method == "POST":
        form = PermissionForm(request.POST, instance=permission)
        if form.is_valid():
            before = {"name": permission.name, "code": permission.code}
            permission = form.save()
            log_activity(
                request.user,
                "rbac.permission.updated",
                f"Updated permission {permission.code}.",
                request=request,
                instance=permission,
                before=before,
                after={"name": permission.name, "code": permission.code},
            )
            messages.success(request, "Permission updated successfully.")
            return redirect("permission_list")
    else:
        form = PermissionForm(instance=permission)
    return render(request, "accounts/permission_form.html", {"form": form, "title": "Edit Permission"})


@login_required
@admin_required
@require_POST
def permission_delete_view(request, pk):
    permission = get_object_or_404(Permission, pk=pk)
    before = {"name": permission.name, "code": permission.code}
    log_activity(
        request.user,
        "rbac.permission.deleted",
        f"Deleted permission {permission.code}.",
        request=request,
        instance=permission,
        before=before,
    )
    permission.delete()
    messages.success(request, "Permission deleted successfully.")
    return redirect("permission_list")


@login_required
@admin_required
def role_permission_list_view(request):
    permissions = RolePermission.objects.select_related("role", "permission").all()
    return render(request, "accounts/role_permission_list.html", {
        "role_permissions": permissions,
        "title": "Role Permissions",
    })


@login_required
@admin_required
def role_permission_add_view(request):
    if request.method == "POST":
        form = RolePermissionForm(request.POST)
        if form.is_valid():
            role_permissions = form.save()
            for role_permission in role_permissions:
                log_activity(
                    request.user,
                    "rbac.role_permission.granted",
                    f"Granted {role_permission.permission.code} to {role_permission.role.slug}.",
                    request=request,
                    instance=role_permission,
                    after={
                        "role": role_permission.role.slug,
                        "permission": role_permission.permission.code,
                    },
                )
            if role_permissions:
                messages.success(
                    request,
                    f"Assigned {len(role_permissions)} permission(s) to the role.",
                )
            else:
                messages.info(
                    request,
                    "All selected permissions were already assigned to this role.",
                )
            return redirect("role_permission_list")
    else:
        form = RolePermissionForm()
    return render(request, "accounts/role_permission_form.html", {"form": form, "title": "Assign Permission to Role"})


@login_required
@admin_required
def access_control_home(request):
    context = {
        "role_count": Role.objects.count(),
        "permission_count": Permission.objects.count(),
        "role_permission_count": RolePermission.objects.count(),
        "module_assignment_count": ModulePermission.objects.count(),
    }
    return render(request, "accounts/access_control_dashboard.html", context)


@login_required
@admin_required
@require_POST
def role_permission_delete_view(request, pk):
    role_permission = get_object_or_404(RolePermission, pk=pk)
    before = {
        "role": role_permission.role.slug,
        "permission": role_permission.permission.code,
    }
    log_activity(
        request.user,
        "rbac.role_permission.revoked",
        f"Revoked {role_permission.permission.code} from {role_permission.role.slug}.",
        request=request,
        instance=role_permission,
        before=before,
    )
    role_permission.delete()
    messages.success(request, "Role permission removed.")
    return redirect("role_permission_list")


@login_required
@admin_required
def user_permission_list_view(request):
    overrides = UserPermission.objects.select_related(
        "user",
        "permission",
        "created_by",
    )
    return render(
        request,
        "accounts/user_permission_list.html",
        {
            "user_permissions": overrides,
            "title": "User Permission Overrides",
        },
    )


@login_required
@admin_required
def user_permission_add_view(request):
    if request.method == "POST":
        form = UserPermissionForm(request.POST)
        if form.is_valid():
            override = form.save(commit=False)
            override.created_by = request.user
            override.save()
            log_activity(
                request.user,
                f"rbac.user_permission.{override.effect}",
                f"{override.effect.title()} override for {override.permission.code} assigned to {override.user.username}.",
                request=request,
                instance=override,
                after={
                    "user": override.user.username,
                    "permission": override.permission.code,
                    "effect": override.effect,
                    "reason": override.reason,
                },
            )
            messages.success(request, "User permission override saved.")
            return redirect("user_permission_list")
    else:
        form = UserPermissionForm()
    return render(
        request,
        "accounts/user_permission_form.html",
        {"form": form, "title": "Add User Permission Override"},
    )


@login_required
@admin_required
@require_POST
def user_permission_delete_view(request, pk):
    override = get_object_or_404(
        UserPermission.objects.select_related("user", "permission"),
        pk=pk,
    )
    before = {
        "user": override.user.username,
        "permission": override.permission.code,
        "effect": override.effect,
        "reason": override.reason,
    }
    log_activity(
        request.user,
        "rbac.user_permission.revoked",
        f"Revoked {override.effect} override for {override.permission.code} from {override.user.username}.",
        request=request,
        instance=override,
        before=before,
    )
    override.delete()
    messages.success(request, "User permission override removed.")
    return redirect("user_permission_list")


@login_required
@admin_required
def admin_panel(request):
    return render(request, "setting/admin_panel.html", {"title": "Admin Panel"})


# ########################################################
# Settings Views
# ########################################################


@login_required
def profile_update(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("profile")
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, "setting/profile_info_change.html", {"form": form})


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect("profile")
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "setting/password_change.html", {"form": form})


# ########################################################
# Staff (Lecturer) Views
# ########################################################


@login_required
@admin_required
def staff_add_view(request):
    if request.method == "POST":
        form = StaffAddForm(request.POST)
        if form.is_valid():
            lecturer = form.save()
            full_name = lecturer.get_full_name
            email = lecturer.email
            messages.success(
                request,
                f"Account for lecturer {full_name} has been created. "
                f"An email with account credentials will be sent to {email} within a minute.",
            )
            return redirect("lecturer_list")
    else:
        form = StaffAddForm()
    return render(
        request, "accounts/add_staff.html", {"title": "Add Lecturer", "form": form}
    )


@login_required
@admin_required
def edit_staff(request, pk):
    lecturer = get_object_or_404(User, is_lecturer=True, pk=pk)
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=lecturer)
        if form.is_valid():
            form.save()
            full_name = lecturer.get_full_name
            messages.success(request, f"Lecturer {full_name} has been updated.")
            return redirect("lecturer_list")
        messages.error(request, "Please correct the error below.")
    else:
        form = ProfileUpdateForm(instance=lecturer)
    return render(
        request, "accounts/edit_lecturer.html", {"title": "Edit Lecturer", "form": form}
    )


@method_decorator([login_required, lecturer_directory_required], name="dispatch")
class LecturerFilterView(FilterView):
    filterset_class = LecturerFilter
    queryset = User.objects.filter(is_lecturer=True)
    template_name = "accounts/lecturer_list.html"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Lecturers"
        return context


@login_required
@admin_required
def render_lecturer_pdf_list(request):
    lecturers = User.objects.filter(is_lecturer=True)
    template_path = "pdf/lecturer_list.html"
    context = {
        "lecturers": lecturers,
        "site_settings": SiteSettings.get_settings(),
    }
    from xhtml2pdf import pisa

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="lecturers_list.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=pdf_link_callback)
    if pisa_status.err:
        return HttpResponse("The lecturer register PDF could not be generated.", status=500)
    return response


@login_required
@admin_required
def delete_staff(request, pk):
    lecturer = get_object_or_404(User, is_lecturer=True, pk=pk)
    full_name = lecturer.get_full_name
    lecturer.delete()
    messages.success(request, f"Lecturer {full_name} has been deleted.")
    return redirect("lecturer_list")


# ########################################################
# Student Views
# ########################################################


@login_required
@student_management_required("students.manage_students")
def student_add_view(request):
    if request.method == "POST":
        form = StudentAddForm(request.POST)
        if form.is_valid():
            student = form.save()
            student_record = Student.objects.get(student=student)
            log_activity(
                request.user,
                "CREATE",
                f"Student record {student_record.registration_number or student_record.pk} created.",
                request=request,
                instance=student_record,
                after={"status": student_record.status},
            )
            full_name = student.get_full_name
            email = student.email
            messages.success(
                request,
                f"Account for {full_name} has been created. "
                f"An email with account credentials will be sent to {email} within a minute.",
            )
            return redirect("student_list")
        messages.error(request, "Correct the error(s) below.")
    else:
        form = StudentAddForm()
    return render(
        request, "accounts/add_student.html", {"title": "Add Student", "form": form}
    )



@method_decorator(login_required, name="dispatch")
class StudentListView(FilterView):
    queryset = Student.objects.select_related("student", "program", "semester").all()
    filterset_class = StudentFilter
    template_name = "accounts/student_list.html"
    paginate_by = 10

    def is_student_self_service(self):
        user = self.request.user
        return user.is_student and not user.is_superuser and not user.is_registrar

    def dispatch(self, request, *args, **kwargs):
        if not self.is_student_self_service() and not user_has_student_management_permission(
            request.user, "students.view_students"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.is_student_self_service():
            return queryset.filter(student=self.request.user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_student_self_service"] = self.is_student_self_service()
        if context["is_student_self_service"]:
            context["title"] = "My Student Record"
            counts = self.get_queryset().values_list("status", flat=True)
            student_statuses = set(counts)
        else:
            context["title"] = "Students"
            student_statuses = None
        context["student_counts"] = [
            {
                "label": label,
                "count": (
                    sum(1 for student_status in student_statuses if student_status == status)
                    if student_statuses is not None
                    else Student.objects.filter(status=status).count()
                ),
            }
            for status, label in Student.Status.choices
        ]
        context["can_manage"] = not context["is_student_self_service"] and user_has_student_management_permission(
            self.request.user, "students.manage_students"
        )
        context["can_export"] = not context["is_student_self_service"] and user_has_student_management_permission(
            self.request.user, "students.export_students"
        )
        return context

@login_required
@student_management_required("students.manage_students")
def edit_student(request, pk):
    student_user = get_object_or_404(User, is_student=True, pk=pk)
    student_profile = get_object_or_404(Student, student=student_user)

    form = StudentEditForm(request.POST or None, request.FILES or None, instance=student_user, student_instance=student_profile)

    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            request.user,
            "UPDATE",
            f"Student record {student_profile.registration_number or student_profile.pk} updated.",
            request=request,
            instance=student_profile,
        )
        messages.success(request, f"Student {student_user.get_full_name} has been updated.")
        return redirect("student_list")

    return render(request, "accounts/edit_student.html", {
        "title": "Edit Student",
        "form": form,
    })

@login_required
@student_management_required("students.export_students")
def render_student_pdf_list(request):
    students = Student.objects.select_related(
        "student",
        "program",
    ).order_by("student__last_name", "student__first_name")
    template_path = "pdf/student_list.html"
    context = {
        "students": students,
        "site_settings": SiteSettings.get_settings(),
    }
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="students_list.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=pdf_link_callback)
    if pisa_status.err:
        return HttpResponse("The student register PDF could not be generated.", status=500)
    return response


@login_required
@student_management_required("students.manage_students")
@require_POST
def delete_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    try:
        transition_student_status(
            student.pk,
            Student.Status.WITHDRAWN,
            request.user,
            request.POST.get("reason", "Administrative withdrawal"),
            request=request,
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect("student_list")
    messages.success(
        request,
        f"Student {student.student.get_full_name} was archived as withdrawn.",
    )
    return redirect("student_list")


@login_required
@student_management_required("students.manage_students")
def edit_student_program(request, pk):
    student = get_object_or_404(Student, student_id=pk)
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = ProgramUpdateForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            log_activity(
                request.user,
                "UPDATE",
                f"Student record {student.registration_number or student.pk} program updated.",
                request=request,
                instance=student,
                after={"program_id": student.program_id},
            )
            full_name = user.get_full_name
            messages.success(request, f"{full_name}'s program has been updated.")
            return redirect("profile_single", user_id=pk)
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = ProgramUpdateForm(instance=student)
    return render(
        request,
        "accounts/edit_student_program.html",
        {"title": "Edit Program", "form": form, "student": student},
    )


@login_required
def student_record_detail(request, pk):
    student = get_object_or_404(
        Student.objects.select_related("student", "program", "semester"),
        pk=pk,
    )
    own_record = request.user.is_active and request.user.pk == student.student_id
    if not own_record and not user_has_student_management_permission(
        request.user, "students.view_students"
    ):
        raise PermissionDenied
    return render(
        request,
        "accounts/student_record_detail.html",
        {
            "student": student,
            "documents": student.documents.all(),
            "status_form": StudentStatusForm(student),
            "document_form": StudentDocumentForm(),
            "can_manage": user_has_student_management_permission(
                request.user, "students.manage_students"
            ),
            "can_manage_documents": user_has_student_management_permission(
                request.user, "students.manage_documents"
            ),
            "can_view_documents": own_record
            or user_has_student_management_permission(
                request.user, "students.view_documents"
            )
            or user_has_student_management_permission(
                request.user, "students.manage_documents"
            ),
        },
    )


@login_required
@student_management_required("students.manage_students")
@require_POST
def student_change_status(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentStatusForm(student, request.POST)
    if form.is_valid():
        try:
            transition_student_status(
                student.pk,
                form.cleaned_data["status"],
                request.user,
                form.cleaned_data["reason"],
                request=request,
            )
        except ValidationError as error:
            form.add_error("status", error)
        else:
            messages.success(request, "Student status was updated.")
            return redirect("student_record_detail", pk=student.pk)
    return render(
        request,
        "accounts/student_record_detail.html",
        {
            "student": student,
            "documents": student.documents.all(),
            "status_form": form,
            "document_form": StudentDocumentForm(),
            "can_manage": True,
            "can_manage_documents": user_has_student_management_permission(
                request.user, "students.manage_documents"
            ),
            "can_view_documents": user_has_student_management_permission(
                request.user, "students.view_documents"
            )
            or user_has_student_management_permission(
                request.user, "students.manage_documents"
            ),
        },
        status=400,
    )


@login_required
@student_management_required("students.manage_documents")
@require_POST
def student_document_upload(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.student = student
        document.uploaded_by = request.user
        document.save()
        log_activity(
            request.user,
            "CREATE",
            f"Document '{document.title}' uploaded for student "
            f"{student.registration_number or student.pk}.",
            request=request,
            instance=document,
            after={"category": document.category},
        )
        messages.success(request, "Student document uploaded.")
        return redirect("student_record_detail", pk=student.pk)
    return render(
        request,
        "accounts/student_record_detail.html",
        {
            "student": student,
            "documents": student.documents.all(),
            "status_form": StudentStatusForm(student),
            "document_form": form,
            "can_manage": user_has_student_management_permission(
                request.user, "students.manage_students"
            ),
            "can_manage_documents": True,
            "can_view_documents": user_has_student_management_permission(
                request.user, "students.view_documents"
            )
            or user_has_student_management_permission(
                request.user, "students.manage_documents"
            ),
        },
        status=400,
    )


@login_required
def student_document_download(request, student_pk, document_pk):
    document = get_object_or_404(
        StudentDocument.objects.select_related("student__student"),
        pk=document_pk,
        student_id=student_pk,
    )
    own_record = (
        request.user.is_active and request.user.pk == document.student.student_id
    )
    if not own_record and not user_has_student_management_permission(
        request.user, "students.view_documents"
    ):
        raise PermissionDenied
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.file.name.rsplit("/", 1)[-1],
    )


# ########################################################
# Parent Views
# ########################################################


@method_decorator([login_required, admin_required], name="dispatch")
class ParentAdd(CreateView):
    model = Parent
    form_class = ParentAddForm
    template_name = "accounts/parent_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Parent added successfully.")
        return super().form_valid(form)



@login_required
@admin_required
def finance_add_view(request):
    if request.method == "POST":
        form = FinanceAddForm(request.POST)
        if form.is_valid():
            # Generate credentials
            username = f"fin{random.randint(1000, 9999)}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            # Create user
            user = form.save(commit=False)
            user.username = username
            user.set_password(password)
            user.is_finance = True
            user.save()

            # Prepare email content
            email_subject = "Finance User Account Created"
            email_body = render_to_string(
                "accounts/email/new_finance_account_confirmation.html",
                {
                    "user": user,
                    "password": password,
                }
            )

            # Send email
            try:
                email = EmailMessage(
                    subject=email_subject,
                    body=email_body,
                    from_email=settings.EMAIL_FROM_ADDRESS,
                    to=[user.email],
                )
                email.content_subtype = "html"
                sent_status = email.send(fail_silently=False)

                if sent_status:
                    messages.success(request, f"Finance user {user.get_full_name} created. Email sent to {user.email}.")
                else:
                    messages.warning(request, f"Finance user {user.get_full_name} created, but email was not sent.")
            except Exception as e:
                messages.error(request, f"Finance user created, but email failed to send: {str(e)}")

            return redirect("finance_user_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = FinanceAddForm()

    return render(request, "accounts/add_finance.html", {
        "form": form,
        "title": "Add Finance User"
    })

@login_required
@admin_required
def finance_user_list(request):
    finance_users = User.objects.filter(is_finance=True)
    return render(request, "accounts/finance_user_list.html", {
        "finance_users": finance_users,
        "title": "Finance Users",
    })

@login_required
@admin_required
def render_finance_pdf_list(request):
    finance_users = User.objects.filter(is_finance=True)
    template_path = "pdf/finance_user_list.html"
    context = {
        "finance_users": finance_users,
        "site_settings": SiteSettings.get_settings(),
    }
    from xhtml2pdf import pisa

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="finance_users_list.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=pdf_link_callback)
    if pisa_status.err:
        return HttpResponse("The finance staff register PDF could not be generated.", status=500)
    return response

@login_required
@admin_required
def edit_finance(request, pk):
    finance_user = get_object_or_404(User, is_finance=True, pk=pk)
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=finance_user)
        if form.is_valid():
            form.save()
            full_name = finance_user.get_full_name
            messages.success(request, f"Finance user {full_name} has been updated.")
            return redirect("finance_user_list")
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = ProfileUpdateForm(instance=finance_user)
    return render(
        request, "accounts/edit_finance.html", {"title": "Edit Finance User", "form": form}
    )


@login_required
@admin_required
def delete_finance(request, pk):
    finance_user = get_object_or_404(User, is_finance=True, pk=pk)
    full_name = finance_user.get_full_name
    finance_user.delete()
    messages.success(request, f"Finance user {full_name} has been deleted.")
    return redirect("finance_user_list")

from .forms import RegistrarAddForm
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

@login_required
@admin_required
def add_registrar_view(request):
    if request.method == "POST":
        form = RegistrarAddForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.generated_password

            email_subject = "Academic Registrar Account Created"
            email_body = render_to_string(
                "accounts/email/new_registrar_account_confirmation.html",
                {"user": user, "password": password}
            )

            email = EmailMessage(
                subject=email_subject,
                body=email_body,
                from_email=settings.EMAIL_FROM_ADDRESS,
                to=[user.email]
            )
            email.content_subtype = "html"
            email.send()

            messages.success(request, f"Registrar {user.get_full_name} created and email sent.")
            return redirect("list_registrars")
    else:
        form = RegistrarAddForm()
    return render(request, "accounts/add_registrar.html", {"form": form, "title": "Add Registrar"})

@login_required
@admin_required
def registrar_list_view(request):
    registrars = User.objects.filter(is_registrar=True)
    return render(request, "accounts/list_registrars.html", {"registrars": registrars, "title": "Registrars"})

@method_decorator([login_required, admin_required], name="dispatch")
class RegistrarListView(FilterView):
    model = User
    template_name = "accounts/list_registrars.html"
    context_object_name = "registrars"

    def get_queryset(self):
        return User.objects.filter(is_registrar=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Academic Registrars"
        return context

def add_registrar_view(request):
    form = RegistrarAddForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("list_registrars")
    return render(request, "accounts/add_registrar.html", {"form": form})


def edit_registrar_view(request, user_id):
    registrar = get_object_or_404(User, id=user_id, is_registrar=True)

    if request.method == 'POST':
        form = RegistrarAddForm(request.POST, instance=registrar)
        if form.is_valid():
            form.save()
            return redirect('list_registrars')
    else:
        form = RegistrarAddForm(instance=registrar)

    return render(request, 'accounts/edit_registrar.html', {
        'form': form,
        'page_title': 'Edit Registrar'
    })

def delete_registrar_view(request, user_id):
    user = get_object_or_404(User, id=user_id, is_registrar=True)
    user.delete()
    return redirect("list_registrars")


def export_registrars_csv(request):
    registrars = User.objects.filter(is_registrar=True)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="registrars.csv"'

    writer = csv.writer(response)
    writer.writerow(["Name", "Email", "Gender", "Phone"])
    for reg in registrars:
        writer.writerow([reg.get_full_name, reg.email, reg.gender, reg.phone])
    return response


def export_registrars_pdf(request):
    registrars = User.objects.filter(is_registrar=True)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="registrars.pdf"'

    p = canvas.Canvas(response)
    p.setFont("Helvetica", 12)
    y = 800
    p.drawString(50, y, "Registrar List")
    y -= 25

    if registrars.exists():
        for i, reg in enumerate(registrars, 1):
            p.drawString(50, y, f"{i}. {reg.first_name} {reg.last_name} | {reg.email} | {reg.gender} | {reg.phone}")
            y -= 20
    else:
        p.drawString(50, y, "No data available.")
        y -= 20

    p.showPage()
    p.save()
    return response

@login_required
@admin_required
def assign_registrar_module_view(request):
    if request.method == 'POST':
        form = RegistrarModulePermissionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('list_registrar_modules')
    else:
        form = RegistrarModulePermissionForm()

    permissions = RegistrarModulePermission.objects.select_related('registrar')
    return render(request, 'accounts/assign_registrar_module.html', {'form': form, 'permissions': permissions})

@login_required
@admin_required
def assign_registrar_module_view(request):
    if request.method == 'POST':
        form = RegistrarModulePermissionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('list_registrar_modules')
    else:
        form = RegistrarModulePermissionForm()

    permissions = RegistrarModulePermission.objects.select_related('registrar')
    return render(request, 'accounts/assign_registrar_module.html', {'form': form, 'permissions': permissions})

@login_required
@admin_required
@require_POST
def revoke_registrar_module_permission(request, pk):
    permission = get_object_or_404(RegistrarModulePermission, pk=pk)
    permission.delete()
    return redirect('list_registrar_modules')


@login_required
@admin_required
def assign_finance_module_view(request):
    finance_users = User.objects.filter(is_finance=True)
    module_choices = FinanceModulePermission._meta.get_field('module_name').choices
    existing_permissions = FinanceModulePermission.objects.select_related('staff')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        module_name = request.POST.get('module_name')

        if user_id and module_name:
            staff = get_object_or_404(User, pk=user_id, is_finance=True)
            exists = FinanceModulePermission.objects.filter(staff=staff, module_name=module_name).exists()

            if not exists:
                FinanceModulePermission.objects.create(staff=staff, module_name=module_name)
                messages.success(request, f'Module "{module_name}" assigned to {staff.get_full_name}')
            else:
                messages.warning(request, 'This module is already assigned.')

        return redirect('assign_finance_module')

    return render(request, 'finance/assign_finance_module.html', {
        'finance_users': finance_users,
        'module_choices': module_choices,
        'existing_permissions': existing_permissions,
    })

@login_required
@admin_required
@require_POST
def revoke_finance_module_permission(request, pk):
    permission = get_object_or_404(FinanceModulePermission, id=pk)
    permission.delete()
    messages.success(request, "Module access has been revoked.")
    return redirect('list_finance_modules')


@login_required
def list_faculty_admins(request):
    faculty_admins = User.objects.filter(is_faculty_admin=True)
    return render(request, "accounts/faculty_admin_list.html", {
        "faculty_admins": faculty_admins,
        "title": "Faculty Admins"
    })



@login_required
@admin_required
def add_faculty_admin_view(request):
    if request.method == "POST":
        form = FacultyAdminAddForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.generated_password

            # Prepare email content
            subject = "Faculty Admin Account Created"
            email_body = render_to_string("accounts/email/new_faculty_admin_account_confirmation.html", {
                "user": user,
                "password": password,
            })

            # Attempt to send email
            try:
                email = EmailMessage(
                    subject=subject,
                    body=email_body,
                    from_email=settings.EMAIL_FROM_ADDRESS,
                    to=[user.email]
                )
                email.content_subtype = "html"
                email.send(fail_silently=False)

                messages.success(request, f"Faculty Admin {user.get_full_name} created and email sent to {user.email}.")
            except Exception as e:
                print("❌ Email send error:", str(e))  # For debugging
                messages.warning(request, f"Faculty Admin created, but email was not sent: {str(e)}")

            return redirect("list_faculty_admins")
        else:
            messages.error(request, "Please correct the error(s) below.")
    else:
        form = FacultyAdminAddForm()

    return render(request, "accounts/add_faculty_admin.html", {"form": form, "title": "Add Faculty Admin"})

@login_required
@admin_required
def edit_faculty_admin_view(request, user_id):
    admin = get_object_or_404(User, id=user_id, is_faculty_admin=True)
    if request.method == "POST":
        form = FacultyAdminAddForm(request.POST, instance=admin)
        if form.is_valid():
            form.save()
            messages.success(request, "Faculty Admin updated successfully.")
            return redirect("list_faculty_admins")
    else:
        form = FacultyAdminAddForm(instance=admin)
    return render(request, "accounts/add_faculty_admin.html", {
        "form": form,
        "title": "Edit Faculty Admin"
    })


@login_required
@admin_required
def delete_faculty_admin_view(request, user_id):
    admin = get_object_or_404(User, id=user_id, is_faculty_admin=True)
    admin.delete()
    messages.success(request, "Faculty Admin deleted successfully.")
    return redirect("list_faculty_admins")


@login_required
@admin_required
def render_faculty_admin_pdf_list(request):
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="faculty_admins_list.pdf"'

    template_path = "pdf/faculty_admin_list.html"
    faculty_admins = User.objects.filter(is_faculty_admin=True)
    html = get_template(template_path).render({
        "faculty_admins": faculty_admins,
        "site_settings": SiteSettings.get_settings(),
    })

    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=pdf_link_callback)
    if pisa_status.err:
        return HttpResponse("The faculty administrator register PDF could not be generated.", status=500)
    return response



from django.shortcuts import render

def permission_denied_view(request):
    return render(request, "403.html", {"title": "Access Denied"})

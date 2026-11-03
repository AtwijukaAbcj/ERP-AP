from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from functools import wraps

from .models import Student

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper


def module_access_required(module_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if (
                user.is_authenticated
                and user.is_active
                and user.can_access_module(module_name)
            ):
                return view_func(request, *args, **kwargs)
            return redirect("permission_denied")

        return wrapper

    return decorator


def lecturer_directory_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.is_lecturer
                or user.can_access_module("lecturers")
            )
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")

    return wrapper


def lecturer_or_module_access_required(module_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if (
                user.is_authenticated
                and user.is_active
                and (
                    user.is_superuser
                    or user.is_lecturer
                    or user.can_access_module("programs")
                    or user.can_access_module("courses")
                    or user.can_access_module(module_name)
                )
            ):
                return view_func(request, *args, **kwargs)
            return redirect("permission_denied")

        return wrapper

    return decorator


def course_catalog_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.is_lecturer
                or user.can_access_module("programs")
                or user.can_access_module("courses")
                or user.can_access_module("assignments")
                or user.can_access_module("quizzes")
            )
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")

    return wrapper


def student_management_required(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not (
                user.is_authenticated
                and user.is_active
                and user_has_student_management_permission(user, permission_code)
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def user_has_student_management_permission(user, permission_code):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True

    override = user.permission_overrides.filter(
        permission__code=permission_code
    ).values_list("effect", flat=True).first()
    if override == "deny":
        return False
    if override == "grant" or user.has_permission(permission_code):
        return True
    if user.has_permission("students"):
        return True
    return user.is_registrar

def lecturer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_lecturer
            or request.user.is_superuser
            or request.user.can_access_module("programs")
            or request.user.can_access_module("courses")
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_student
            and Student.objects.filter(student_id=request.user.pk).exists()
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def faculty_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_faculty_admin
            or request.user.can_access_module("faculties")
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def lecturer_or_faculty_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (
            request.user.is_lecturer
            or request.user.is_faculty_admin
            or request.user.is_superuser
            or request.user.can_access_module("programs")
            or request.user.can_access_module("courses")
            or request.user.can_access_module("faculties")
        ):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def admin_or_faculty_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_superuser or request.user.is_faculty_admin):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

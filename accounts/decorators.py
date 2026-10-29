from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
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
    return user.is_registrar

def lecturer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_lecturer or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_student or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def faculty_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_faculty_admin:
            return view_func(request, *args, **kwargs)
        return redirect("permission_denied")
    return wrapper

def lecturer_or_faculty_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_lecturer or request.user.is_faculty_admin):
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

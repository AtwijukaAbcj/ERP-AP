from functools import wraps

from django.core.exceptions import PermissionDenied


def has_procurement_access(user, *permission_codes):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if user.permission_overrides.filter(
        permission__code__in=permission_codes,
        effect="deny",
    ).exists():
        return False
    if user.has_permission("procurement"):
        return True
    if any(user.has_permission(code) for code in permission_codes):
        return True
    return bool(
        user.is_procurement_manager
        or user.has_role("procurement_manager")
    )


def procurement_permission_required(*permission_codes):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_procurement_access(request.user, *permission_codes):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

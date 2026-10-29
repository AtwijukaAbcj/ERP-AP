from functools import wraps

from django.core.exceptions import PermissionDenied


def has_finance_permission(user, *permission_codes):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser or user.is_finance_manager:
        return True
    if any(user.has_permission(code) for code in permission_codes):
        return True
    if user.is_accountant and any(
        code in {
            "create_invoice",
            "manage_invoices",
            "view_student_invoices",
        }
        for code in permission_codes
    ):
        return True
    if user.is_finance:
        from .models import FinanceModulePermission

        return FinanceModulePermission.objects.filter(
            staff=user,
            module_name__in=permission_codes,
        ).exists()
    return False


def finance_permission_required(*permission_codes):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_finance_permission(request.user, *permission_codes):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

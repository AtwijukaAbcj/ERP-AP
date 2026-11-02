from functools import wraps

from django.core.exceptions import PermissionDenied


def admissions_permission(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not (
                user.is_authenticated
                and user.is_active
                and (
                    user.is_superuser
                    or user.has_permission(permission_code)
                    or (
                        not user.permission_overrides.filter(
                            permission__code=permission_code,
                            effect="deny",
                        ).exists()
                        and (user.is_registrar or user.has_permission("admissions"))
                    )
                )
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

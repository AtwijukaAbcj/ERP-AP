from functools import wraps

from django.core.exceptions import PermissionDenied


def clinical_permission(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not (
                user.is_authenticated
                and user.is_active
                and (
                    user.has_permission(permission_code)
                    or (
                        not user.permission_overrides.filter(
                            permission__code=permission_code,
                            effect="deny",
                        ).exists()
                        and user.has_permission("clinical")
                    )
                )
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

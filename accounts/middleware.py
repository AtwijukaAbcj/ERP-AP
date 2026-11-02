from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin


MODULE_ACCESS_BY_APP = {
    "assignment": "assignments",
    "quiz": "quizzes",
    "result": "results",
    "voting": "voting",
    "audit": "audit",
}


class AssignedModuleAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated:
            return None
        if not user.is_active:
            raise PermissionDenied
        if user.is_superuser:
            return None

        view_class = getattr(view_func, "view_class", None)
        view_module = view_class.__module__ if view_class else view_func.__module__
        app_label = view_module.split(".", 1)[0]
        module_name = MODULE_ACCESS_BY_APP.get(app_label)
        if module_name and not user.can_access_module(module_name):
            raise PermissionDenied
        return None

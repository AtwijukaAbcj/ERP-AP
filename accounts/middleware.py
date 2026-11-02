from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from accounts.models import User


MODULE_ACCESS_BY_APP = {
    "assignment": "assignments",
    "quiz": "quizzes",
    "result": "results",
    "voting": "voting",
    "audit": "audit",
}


class OnlineUserTrackingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return None

        now = timezone.now()
        User.objects.filter(pk=user.pk).filter(
            Q(last_activity__isnull=True)
            | Q(last_activity__lt=now - timedelta(minutes=1))
        ).update(last_activity=now)
        return None


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

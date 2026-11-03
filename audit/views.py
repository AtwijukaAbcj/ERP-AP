from django.views.generic import ListView
from .models import ActivityLog
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from accounts.decorators import module_access_required
from django.utils.decorators import method_decorator

@method_decorator(
    [login_required, module_access_required("audit")],
    name="dispatch",
)
class ActivityLogListView(LoginRequiredMixin, ListView):
    model = ActivityLog
    template_name = 'audit/activity_log_list.html'
    context_object_name = 'logs'

    def get_queryset(self):
        return ActivityLog.objects.select_related("user").all()

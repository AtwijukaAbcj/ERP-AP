from django.contrib import admin
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "target_model", "object_id", "timestamp", "ip_address")
    list_filter = ("user", "timestamp")
    search_fields = ("user__username", "action", "description", "target_model", "object_id", "ip_address")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

from django.contrib import admin

from .models import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
)


class ApplicationStatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "comment", "changed_by", "changed_at")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "application_number",
        "first_name",
        "last_name",
        "program",
        "intake",
        "status",
        "created_at",
    )
    list_filter = ("status", "program", "intake", "academic_year")
    search_fields = (
        "application_number",
        "first_name",
        "last_name",
        "email",
        "phone",
    )
    readonly_fields = ("application_number", "created_at", "updated_at")
    inlines = (ApplicationStatusHistoryInline,)


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("application", "from_status", "to_status", "changed_by", "changed_at")
    readonly_fields = (
        "application",
        "from_status",
        "to_status",
        "comment",
        "changed_by",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApplicationStatus)
class ApplicationStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    readonly_fields = ("code",)

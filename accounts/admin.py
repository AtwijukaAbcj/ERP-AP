from django.contrib import admin
from .models import (
    Parent,
    Role,
    RolePermission,
    Student,
    StudentStatusHistory,
    User,
    Permission,
)


class UserAdmin(admin.ModelAdmin):
    list_display = [
        "get_full_name",
        "username",
        "email",
        "role",
        "is_active",
        "is_student",
        "is_lecturer",
        'is_finance',
        "is_parent",
        "is_staff",
    ]
    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_lecturer",
        "is_parent",
        "is_staff",
    ]

    class Meta:
        managed = True
        verbose_name = "User"
        verbose_name_plural = "Users"


admin.site.register(User, UserAdmin)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "student", "program", "cohort", "status")
    list_filter = ("status", "program", "cohort")
    search_fields = (
        "registration_number",
        "student__first_name",
        "student__last_name",
        "student__email",
    )
    readonly_fields = ("status",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentStatusHistory)
class StudentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("student", "from_status", "to_status", "changed_by", "changed_at")
    readonly_fields = (
        "student",
        "from_status",
        "to_status",
        "reason",
        "changed_by",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Parent)
admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(RolePermission)

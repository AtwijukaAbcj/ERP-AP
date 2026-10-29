from django.contrib import admin
from .models import (
    SupplierCategory,
    Supplier,
    ProcurementDepartment,
    ProcurementStatus,
    ProcurementWorkflowRule,
    ProcurementPlan,
    PurchaseRequisition,
    PurchaseOrder,
    PurchaseQuotation,
    PurchaseQuotationItem,
)


@admin.register(SupplierCategory)
class SupplierCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'is_blacklisted')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('is_blacklisted', 'category')


@admin.register(ProcurementDepartment)
class ProcurementDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(ProcurementStatus)
class ProcurementStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_default')
    search_fields = ('name', 'slug')
    list_filter = ('is_default',)


@admin.register(ProcurementWorkflowRule)
class ProcurementWorkflowRuleAdmin(admin.ModelAdmin):
    list_display = (
        "action_label",
        "from_status",
        "to_status",
        "department",
        "approver_type",
        "is_active",
    )
    list_filter = ("is_active", "approver_type", "department")
    search_fields = ("action_label", "from_status__name", "to_status__name")


@admin.register(ProcurementPlan)
class ProcurementPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'fiscal_year', 'approved')
    list_filter = ('fiscal_year', 'approved')


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'status', 'requested_by', 'total_amount')
    list_filter = ('status', 'department')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'order_date', 'total_amount', 'approved')
    list_filter = ('approved',)


class PurchaseQuotationItemInline(admin.TabularInline):
    model = PurchaseQuotationItem
    extra = 0


@admin.register(PurchaseQuotation)
class PurchaseQuotationAdmin(admin.ModelAdmin):
    list_display = ("supplier", "date_received", "valid_until", "status", "total_amount")
    list_filter = ("status", "date_received")
    search_fields = ("reference", "supplier__name")
    inlines = (PurchaseQuotationItemInline,)

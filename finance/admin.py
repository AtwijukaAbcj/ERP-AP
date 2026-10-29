from django.contrib import admin
from .models import (
    AccountPayable,
    AccountReceivable,
    BankReconciliation,
    Budget,
    CashBookEntry,
    Expense,
    ExpenseCategory,
    FeeCategory,
    FinanceModulePermission,
    GeneralLedgerEntry,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    LedgerAccount,
    OnlineInvoicePayment,
    Payroll,
    PaymentVoucher,
    PettyCashEntry,
    Staff,
    StaffCategory,
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'semester')
    list_filter = ('semester',)
    search_fields = ('name', 'description')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'semester', 'date_issued', 'due_date', 'total_amount', 'paid_amount', 'status')
    list_filter = ('status', 'semester', 'date_issued')
    search_fields = ('student__user__username', 'student__user__first_name', 'student__user__last_name')
    inlines = [InvoiceItemInline]
    readonly_fields = ('date_issued',)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'category', 'amount')
    list_filter = ('category',)


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "payment_date", "amount", "method", "reference", "recorded_by")
    list_filter = ("method", "payment_date")
    search_fields = ("invoice__student__student__username", "reference")
    readonly_fields = ("invoice", "amount", "payment_date", "method", "reference", "recorded_by", "created_at")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OnlineInvoicePayment)
class OnlineInvoicePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "provider",
        "status",
        "amount",
        "currency",
        "provider_reference",
        "created_at",
    )
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = (
        "invoice__student__student__username",
        "provider_session_id",
        "provider_reference",
    )
    readonly_fields = tuple(field.name for field in OnlineInvoicePayment._meta.fields)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'fiscal_year', 'amount', 'approved', 'requested_by')
    list_filter = ('approved', 'fiscal_year', 'department')
    search_fields = ('title', 'department', 'requested_by__username')


@admin.register(CashBookEntry)
class CashBookEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'reference', 'debit', 'credit', 'created_by')
    list_filter = ('date',)


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'statement_date', 'book_balance', 'bank_balance', 'reconciled')
    list_filter = ('reconciled', 'statement_date')


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(GeneralLedgerEntry)
class GeneralLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'account', 'debit', 'credit', 'created_by')
    list_filter = ('date', 'account')


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('voucher_number', 'title', 'vendor_name', 'amount', 'status', 'approved')
    list_filter = ('status', 'approved')


@admin.register(FinanceModulePermission)
class FinanceModulePermissionAdmin(admin.ModelAdmin):
    list_display = ('staff', 'module_name')
    list_filter = ('module_name',)
    search_fields = ('staff__username', 'staff__first_name', 'staff__last_name')


@admin.register(StaffCategory)
class StaffCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'category', 'job_title', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'employee_id')


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('staff', 'period_start', 'period_end', 'gross_amount', 'net_amount', 'status')
    list_filter = ('status',)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'amount', 'date', 'paid_by')
    list_filter = ('category', 'date')


@admin.register(PettyCashEntry)
class PettyCashAdmin(admin.ModelAdmin):
    list_display = ('date', 'amount', 'created_by')


@admin.register(AccountPayable)
class AccountPayableAdmin(admin.ModelAdmin):
    list_display = ('vendor_name', 'amount', 'due_date', 'paid')
    list_filter = ('paid',)


@admin.register(AccountReceivable)
class AccountReceivableAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'amount', 'due_date', 'received')
    list_filter = ('received',)

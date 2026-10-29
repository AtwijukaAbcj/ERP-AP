import uuid

from django.db import models
from accounts.models import Student
from django.db import models
from accounts.models import User
from core.models import Semester
from course.models import Faculty

MODULE_CHOICES = [
    ("fee_category_add", "Add Fee Category"),
    ("manage_fee_categories", "Manage Fee Categories"),
    ("create_invoice", "Create Invoice"),
    ("manage_invoices", "Manage Invoices"),
    ("view_student_invoices", "View Student Invoices"),
    ("staff_category_list", "Staff Categories"),
    ("staff_list", "Staff Members"),
    ("staff_manage", "Manage Staff Records"),
    ("department_list", "Staff Departments"),
    ("department_manage", "Manage Staff Departments"),
    ("payroll_list", "Payroll"),
    ("expense_category_list", "Expense Categories"),
    ("expense_list", "Expenses"),
    ("petty_cash_list", "Petty Cash"),
    ("accounts_payable_list", "Accounts Payable"),
    ("accounts_receivable_list", "Accounts Receivable"),
    ("budget_list", "Budgets"),
    ("cash_book_list", "Cash Book"),
    ("bank_reconciliation_list", "Bank Reconciliation"),
    ("ledger_account_list", "Ledger Accounts"),
    ("general_ledger_list", "General Ledger"),
    ("payment_voucher_list", "Payment Vouchers"),
    ("finance_reports", "Finance Reports"),
]

class FinanceModulePermission(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_finance': True})
    module_name = models.CharField(max_length=50, choices=MODULE_CHOICES)

    def __str__(self):
        return f"{self.staff.get_full_name} - {self.get_module_name_display()}"


class FeeCategory(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = "Fee Category"
        verbose_name_plural = "Fee Categories"

    def __str__(self):
        student_part = f" - {self.student.student.get_full_name}" if self.student else ""
        return f"{self.name} ({self.semester}){student_part}"


class Invoice(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date_issued = models.DateField(auto_now_add=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('paid', 'Paid'), ('partial', 'Partially Paid')],
        default='pending'
    )

    @property
    def balance(self):
        return (self.total_amount or 0) - (self.paid_amount or 0)

    def update_status(self):
        if self.paid_amount >= self.total_amount:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'
        self.save()

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    category = models.ForeignKey(FeeCategory, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.category.name} - {self.amount}"


class InvoicePayment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank transfer"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CARD = "card", "Card"
        PAYPAL = "paypal", "PayPal"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    method = models.CharField(max_length=20, choices=Method.choices)
    reference = models.CharField(max_length=120, blank=True)
    recorded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_invoice_payments_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-payment_date", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="invoice_payment_amount_positive",
            )
        ]

    def __str__(self):
        return f"Payment of {self.amount} for invoice {self.invoice_id}"


class OnlineInvoicePayment(models.Model):
    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="online_payment_attempts",
    )
    provider = models.CharField(max_length=10, choices=Provider.choices)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider_session_id = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True,
    )
    provider_redirect_url = models.URLField(max_length=500, blank=True)
    provider_reference = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True,
    )
    invoice_payment = models.OneToOneField(
        InvoicePayment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="online_attempt",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="online_invoice_payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=("invoice",),
                condition=models.Q(status="pending"),
                name="single_pending_online_payment_per_invoice",
            ),
        ]
        ordering = ("-created_at",)


class Budget(models.Model):
    title = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    fiscal_year = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    requested_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_budgets')
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budgets')
    approved_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'

    def __str__(self):
        return f"{self.title} ({self.fiscal_year})"


class CashBookEntry(models.Model):
    date = models.DateField()
    reference = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ('-date',)
        verbose_name = 'Cash Book Entry'
        verbose_name_plural = 'Cash Book Entries'

    def __str__(self):
        return f"{self.date} - {self.description or self.reference or 'Cash Entry'}"


class BankReconciliation(models.Model):
    bank_name = models.CharField(max_length=255)
    statement_date = models.DateField()
    book_balance = models.DecimalField(max_digits=12, decimal_places=2)
    bank_balance = models.DecimalField(max_digits=12, decimal_places=2)
    reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(blank=True, null=True)
    reconciled_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_reconciliations')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Bank Reconciliation'
        verbose_name_plural = 'Bank Reconciliations'

    def __str__(self):
        return f"{self.bank_name} - {self.statement_date}"


class LedgerAccount(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Ledger Account'
        verbose_name_plural = 'Ledger Accounts'

    def __str__(self):
        return f"{self.code} - {self.name}"


class GeneralLedgerEntry(models.Model):
    account = models.ForeignKey(LedgerAccount, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    reference = models.CharField(max_length=120, blank=True, null=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ('-date',)
        verbose_name = 'General Ledger Entry'
        verbose_name_plural = 'General Ledger Entries'

    def __str__(self):
        return f"{self.date} - {self.account.code} - {self.description or self.reference}"


class PaymentVoucher(models.Model):
    voucher_number = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    requested_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_vouchers')
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vouchers')
    approved_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('draft', 'Draft'), ('pending', 'Pending'), ('approved', 'Approved'), ('paid', 'Paid'), ('rejected', 'Rejected')], default='draft')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Payment Voucher'
        verbose_name_plural = 'Payment Vouchers'

    def __str__(self):
        return f"{self.voucher_number} - {self.vendor_name}"


# --- Staff, Payroll and Accounting Models ---


class StaffCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Staff Category"
        verbose_name_plural = "Staff Categories"

    def __str__(self):
        return self.name


class StaffDepartment(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    faculty = models.ForeignKey(
        Faculty,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_departments",
    )
    head = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_staff_departments",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    category = models.ForeignKey(StaffCategory, null=True, blank=True, on_delete=models.SET_NULL)
    qualification = models.CharField(max_length=200, blank=True)
    department = models.ForeignKey(
        StaffDepartment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_members",
    )
    employee_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    job_title = models.CharField(max_length=120, blank=True, null=True)
    date_hired = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-date_hired",)

    def __str__(self):
        return f"{self.user.get_full_name} ({self.employee_id or 'no-id'})"


class Payroll(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("partial", "Partially Paid"),
    ]

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="payrolls")
    period_start = models.DateField()
    period_end = models.DateField()
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    class Meta:
        ordering = ("-period_end",)

    def __str__(self):
        return f"Payroll {self.staff} {self.period_start} - {self.period_end}"


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    category = models.ForeignKey(ExpenseCategory, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    paid_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    reference = models.CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"


class PettyCashEntry(models.Model):
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"PettyCash {self.date} - {self.amount}"


class AccountPayable(models.Model):
    vendor_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    paid = models.BooleanField(default=False)
    reference = models.CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f"AP {self.vendor_name} - {self.amount}"


class AccountReceivable(models.Model):
    customer_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    received = models.BooleanField(default=False)
    reference = models.CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f"AR {self.customer_name} - {self.amount}"

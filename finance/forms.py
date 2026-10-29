# finance/forms.py

from decimal import Decimal

from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from course.models import Faculty
from .models import (
    AccountPayable,
    AccountReceivable,
    BankReconciliation,
    Budget,
    CashBookEntry,
    Expense,
    ExpenseCategory,
    FeeCategory,
    GeneralLedgerEntry,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    LedgerAccount,
    PaymentVoucher,
    Staff,
    StaffCategory,
    StaffDepartment,
    Payroll,
    PettyCashEntry,
)


class DateInput(forms.DateInput):
    input_type = 'date'
from accounts.models import Student, User
from core.models import Semester


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = [
            'title',
            'department',
            'fiscal_year',
            'amount',
            'requested_by',
            'approved',
            'approved_by',
            'notes',
        ]


class CashBookEntryForm(forms.ModelForm):
    class Meta:
        model = CashBookEntry
        fields = ['date', 'reference', 'description', 'debit', 'credit', 'created_by']
        widgets = {
            'date': DateInput(),
        }


class BankReconciliationForm(forms.ModelForm):
    class Meta:
        model = BankReconciliation
        fields = [
            'bank_name',
            'statement_date',
            'book_balance',
            'bank_balance',
            'reconciled',
            'reconciled_by',
            'notes',
        ]
        widgets = {
            'statement_date': DateInput(),
        }


class LedgerAccountForm(forms.ModelForm):
    class Meta:
        model = LedgerAccount
        fields = ['code', 'name', 'description']


class GeneralLedgerEntryForm(forms.ModelForm):
    class Meta:
        model = GeneralLedgerEntry
        fields = ['account', 'date', 'description', 'reference', 'debit', 'credit', 'created_by']
        widgets = {
            'date': DateInput(),
        }


class PaymentVoucherForm(forms.ModelForm):
    class Meta:
        model = PaymentVoucher
        fields = [
            'voucher_number',
            'title',
            'vendor_name',
            'amount',
            'requested_by',
            'status',
            'approved',
            'approved_by',
            'notes',
        ]


class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'amount', 'semester', 'student']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_semester = Semester.objects.filter(is_current_semester=True).first()
        if current_semester:
            self.fields['semester'].initial = current_semester
        self.fields['student'].required = False
        self.fields['student'].queryset = Student.objects.select_related('student').all()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Fee amount must be greater than zero.")
        return amount


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['student', 'semester', 'due_date']
        widgets = {
            'due_date': DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_semester = Semester.objects.filter(is_current_semester=True).first()
        if current_semester:
            self.fields['semester'].initial = current_semester


class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = InvoicePayment
        fields = ["amount", "payment_date", "method", "reference"]
        widgets = {"payment_date": DateInput()}

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount


class SemesterInvoiceGenerationForm(forms.Form):
    due_date = forms.DateField(widget=DateInput())


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['category', 'amount']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = True
        self.fields['amount'].min_value = Decimal("0.01")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Invoice item amount must be greater than zero.")
        return amount


class BaseInvoiceItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        item_total = Decimal("0.00")
        active_items = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            category = form.cleaned_data.get("category")
            amount = form.cleaned_data.get("amount")
            if category is None or amount is None:
                continue
            active_items += 1
            item_total += amount
            if category.semester_id != self.instance.semester_id:
                self.add_error(None, "Each fee category must belong to the invoice semester.")
            if category.student_id not in (None, self.instance.student_id):
                self.add_error(None, "A student-specific fee can only be invoiced to that student.")

        if active_items == 0 or item_total <= Decimal("0.00"):
            self.add_error(None, "An invoice must contain at least one positive fee item.")

        if self.instance.pk and item_total < self.instance.paid_amount:
            self.add_error(None, "Invoice items cannot reduce the total below the amount already paid.")


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    formset=BaseInvoiceItemFormSet,
    fields=('category', 'amount'),
    extra=1,
    can_delete=True,
)


class StaffCategoryForm(forms.ModelForm):
    class Meta:
        model = StaffCategory
        fields = ['name', 'description']


class StaffDepartmentForm(forms.ModelForm):
    class Meta:
        model = StaffDepartment
        fields = ['name', 'code', 'faculty', 'head', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['faculty'].queryset = Faculty.objects.order_by('name')
        self.fields['head'].queryset = User.objects.filter(
            is_active=True,
            is_staff=True,
        ).order_by('first_name', 'last_name', 'username')
        self.fields['head'].required = False


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = [
            'user',
            'category',
            'qualification',
            'department',
            'employee_id',
            'job_title',
            'date_hired',
            'is_active',
        ]
        widgets = {'date_hired': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        eligible_users = User.objects.filter(
            is_staff=True,
            is_active=True,
        )
        existing_staff_user_id = getattr(self.instance, 'user_id', None)
        if existing_staff_user_id:
            eligible_users = eligible_users.filter(
                Q(pk=existing_staff_user_id) | Q(staff__isnull=True)
            )
        else:
            eligible_users = eligible_users.filter(staff__isnull=True)
        self.fields['user'].queryset = eligible_users.order_by(
            'first_name',
            'last_name',
            'username',
        )
        departments = StaffDepartment.objects.filter(is_active=True)
        existing_department_id = getattr(self.instance, 'department_id', None)
        if existing_department_id:
            departments = StaffDepartment.objects.filter(
                Q(is_active=True) | Q(pk=existing_department_id)
            )
        self.fields['department'].queryset = departments.order_by('name')


class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = ['staff', 'period_start', 'period_end', 'gross_amount', 'deductions', 'net_amount', 'paid_date', 'status']
        widgets = {
            'period_start': DateInput(),
            'period_end': DateInput(),
            'paid_date': DateInput(),
        }


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name']


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'title', 'amount', 'date', 'paid_by', 'reference']
        widgets = {
            'date': DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paid_by'].queryset = User.objects.filter(is_active=True)
        self.fields['paid_by'].required = False


class PettyCashEntryForm(forms.ModelForm):
    class Meta:
        model = PettyCashEntry
        fields = ['date', 'amount', 'description', 'created_by']
        widgets = {
            'date': DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['created_by'].queryset = User.objects.filter(is_active=True)
        self.fields['created_by'].required = False


class AccountPayableForm(forms.ModelForm):
    class Meta:
        model = AccountPayable
        fields = ['vendor_name', 'description', 'amount', 'due_date', 'paid', 'reference']
        widgets = {
            'due_date': DateInput(),
        }


class AccountReceivableForm(forms.ModelForm):
    class Meta:
        model = AccountReceivable
        fields = ['customer_name', 'description', 'amount', 'due_date', 'received', 'reference']
        widgets = {
            'due_date': DateInput(),
        }

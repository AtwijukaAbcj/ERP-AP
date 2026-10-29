from rest_framework import serializers
from .models import (
    FeeCategory,
    Invoice,
    InvoiceItem,
    StaffCategory,
    Staff,
    StaffDepartment,
    Payroll,
    ExpenseCategory,
    Expense,
    PettyCashEntry,
    AccountPayable,
    AccountReceivable,
)


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ["id", "name", "description", "amount", "semester", "student"]

    def validate_amount(self, amount):
        if amount <= 0:
            raise serializers.ValidationError("Fee amount must be greater than zero.")
        return amount


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["id", "category", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "student",
            "date_issued",
            "semester",
            "due_date",
            "total_amount",
            "paid_amount",
            "status",
            "balance",
            "items",
        ]
        read_only_fields = [
            "date_issued",
            "paid_amount",
            "status",
            "items",
        ]

    def validate_total_amount(self, amount):
        if amount <= 0:
            raise serializers.ValidationError("Invoice total must be greater than zero.")
        if self.instance and amount < self.instance.paid_amount:
            raise serializers.ValidationError(
                "The invoice total cannot be lower than the amount already paid."
            )
        return amount

    def update(self, instance, validated_data):
        invoice = super().update(instance, validated_data)
        invoice.update_status()
        return invoice

    def get_balance(self, obj):
        return obj.balance


class StaffCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffCategory
        fields = ["id", "name", "description"]


class StaffDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffDepartment
        fields = ["id", "name", "code", "faculty", "head", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate_head(self, head):
        if head and (not head.is_active or not head.is_staff):
            raise serializers.ValidationError(
                "Department heads must be active staff users."
            )
        return head


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = [
            "id",
            "user",
            "category",
            "department",
            "employee_id",
            "job_title",
            "date_hired",
            "is_active",
        ]

    def validate_department(self, department):
        if department and not department.is_active:
            raise serializers.ValidationError(
                "Inactive departments cannot be assigned to staff."
            )
        return department


class PayrollSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payroll
        fields = [
            "id",
            "staff",
            "period_start",
            "period_end",
            "gross_amount",
            "deductions",
            "net_amount",
            "paid_date",
            "status",
        ]


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name"]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id", "category", "title", "amount", "date", "paid_by", "reference"]


class PettyCashEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PettyCashEntry
        fields = ["id", "date", "amount", "description", "created_by"]


class AccountPayableSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountPayable
        fields = ["id", "vendor_name", "description", "amount", "due_date", "paid", "reference"]


class AccountReceivableSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountReceivable
        fields = ["id", "customer_name", "description", "amount", "due_date", "received", "reference"]

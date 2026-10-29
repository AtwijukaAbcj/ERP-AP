from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import (
    FeeCategory,
    Invoice,
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
from .serializers import (
    FeeCategorySerializer,
    InvoiceSerializer,
    StaffCategorySerializer,
    StaffSerializer,
    StaffDepartmentSerializer,
    PayrollSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    PettyCashEntrySerializer,
    AccountPayableSerializer,
    AccountReceivableSerializer,
)
from accounts.permissions import IsFinanceManager, IsAccountant


class FeeCategoryViewSet(viewsets.ModelViewSet):
    queryset = FeeCategory.objects.all().order_by("name")
    serializer_class = FeeCategorySerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by("-date_issued")
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsAccountant]


class StaffCategoryViewSet(viewsets.ModelViewSet):
    queryset = StaffCategory.objects.all().order_by("name")
    serializer_class = StaffCategorySerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.select_related(
        "user",
        "category",
        "department",
    ).all().order_by("user__first_name")
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class StaffDepartmentViewSet(viewsets.ModelViewSet):
    queryset = StaffDepartment.objects.select_related("faculty", "head").all()
    serializer_class = StaffDepartmentSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class PayrollViewSet(viewsets.ModelViewSet):
    queryset = Payroll.objects.all().order_by("-period_end")
    serializer_class = PayrollSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by("name")
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by("-date")
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class PettyCashEntryViewSet(viewsets.ModelViewSet):
    queryset = PettyCashEntry.objects.all().order_by("-date")
    serializer_class = PettyCashEntrySerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class AccountPayableViewSet(viewsets.ModelViewSet):
    queryset = AccountPayable.objects.all().order_by("due_date")
    serializer_class = AccountPayableSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]


class AccountReceivableViewSet(viewsets.ModelViewSet):
    queryset = AccountReceivable.objects.all().order_by("due_date")
    serializer_class = AccountReceivableSerializer
    permission_classes = [IsAuthenticated, IsFinanceManager]

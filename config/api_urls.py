from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views_api import UserViewSet, RoleViewSet, PermissionViewSet
from finance.views_api import (
    FeeCategoryViewSet,
    InvoiceViewSet,
    StaffCategoryViewSet,
    StaffViewSet,
    StaffDepartmentViewSet,
    PayrollViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    PettyCashEntryViewSet,
    AccountPayableViewSet,
    AccountReceivableViewSet,
)
from procurement.views_api import (
    SupplierCategoryViewSet as ProcurementSupplierCategoryViewSet,
    SupplierViewSet as ProcurementSupplierViewSet,
    ProcurementPlanViewSet,
    PurchaseRequisitionViewSet,
    PurchaseOrderViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'staff-categories', StaffCategoryViewSet, basename='staff-category')
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'staff-departments', StaffDepartmentViewSet, basename='staff-department')
router.register(r'payrolls', PayrollViewSet, basename='payroll')
router.register(r'expense-categories', ExpenseCategoryViewSet, basename='expense-category')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'petty-cash', PettyCashEntryViewSet, basename='petty-cash')
router.register(r'accounts-payable', AccountPayableViewSet, basename='account-payable')
router.register(r'accounts-receivable', AccountReceivableViewSet, basename='account-receivable')
router.register(
    r'procurement/supplier-categories',
    ProcurementSupplierCategoryViewSet,
    basename='procurement-supplier-category',
)
router.register(
    r'procurement/suppliers',
    ProcurementSupplierViewSet,
    basename='procurement-supplier',
)
router.register(
    r'procurement/plans',
    ProcurementPlanViewSet,
    basename='procurement-plan',
)
router.register(
    r'procurement/requisitions',
    PurchaseRequisitionViewSet,
    basename='procurement-requisition',
)
router.register(
    r'procurement/orders',
    PurchaseOrderViewSet,
    basename='procurement-order',
)

urlpatterns = [
    path('', include(router.urls)),
]

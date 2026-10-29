import os
import django
from typing import Any
from faker import Faker
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import (
    ROLE_ACCOUNTANT,
    ROLE_FINANCE_MANAGER,
    ROLE_PROCUREMENT_MANAGER,
    ROLE_PROCUREMENT_OFFICER,
    Role,
    User,
)
from finance.models import (
    AccountPayable,
    AccountReceivable,
    BankReconciliation,
    Budget,
    CashBookEntry,
    Expense,
    ExpenseCategory,
    FinanceModulePermission,
    GeneralLedgerEntry,
    LedgerAccount,
    PaymentVoucher,
)
from procurement.models import (
    SupplierCategory,
    Supplier,
    ProcurementDepartment,
    ProcurementStatus,
    ProcurementPlan,
    PurchaseOrder,
    PurchaseRequisition,
)

fake = Faker()


def _get_or_create_role(slug: str, name: str) -> Role:
    role, _ = Role.objects.get_or_create(slug=slug, defaults={"name": name})
    if role.name != name:
        role.name = name
        role.save(update_fields=["name"])
    return role


def _get_or_create_user(username: str, email: str, first_name: str, last_name: str, password: str = "Password123", **extra_fields: Any) -> User:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            **extra_fields,
        },
    )

    if created:
        user.set_password(password)
        user.save()
        return user

    # Keep the user updated for repeatable script execution.
    changed = False

    for field_name, field_value in {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        **extra_fields,
    }.items():
        if getattr(user, field_name) != field_value:
            setattr(user, field_name, field_value)
            changed = True

    if changed:
        user.set_password(password)
        user.save()

    return user


def generate_finance_and_procurement_users() -> list[User]:
    """Create sample finance and procurement users for privilege testing."""
    finance_manager_role = _get_or_create_role(ROLE_FINANCE_MANAGER, "Finance Manager")
    accountant_role = _get_or_create_role(ROLE_ACCOUNTANT, "Accountant")
    procurement_officer_role = _get_or_create_role(ROLE_PROCUREMENT_OFFICER, "Procurement Officer")
    procurement_manager_role = _get_or_create_role(ROLE_PROCUREMENT_MANAGER, "Procurement Manager")

    users = [
        _get_or_create_user(
            username="finance_manager_flag",
            email="finance_manager_flag@erp.local",
            first_name="Finance",
            last_name="ManagerFlag",
            is_finance=True,
            is_finance_manager=True,
        ),
        _get_or_create_user(
            username="finance_manager_role",
            email="finance_manager_role@erp.local",
            first_name="Finance",
            last_name="ManagerRole",
            role=finance_manager_role,
        ),
        _get_or_create_user(
            username="accountant_flag",
            email="accountant_flag@erp.local",
            first_name="Accountant",
            last_name="Flag",
            is_finance=True,
            is_accountant=True,
        ),
        _get_or_create_user(
            username="accountant_role",
            email="accountant_role@erp.local",
            first_name="Accountant",
            last_name="Role",
            role=accountant_role,
        ),
        _get_or_create_user(
            username="procurement_officer_flag",
            email="procurement_officer_flag@erp.local",
            first_name="Procurement",
            last_name="OfficerFlag",
            is_procurement_officer=True,
        ),
        _get_or_create_user(
            username="procurement_officer_role",
            email="procurement_officer_role@erp.local",
            first_name="Procurement",
            last_name="OfficerRole",
            role=procurement_officer_role,
        ),
        _get_or_create_user(
            username="procurement_manager_flag",
            email="procurement_manager_flag@erp.local",
            first_name="Procurement",
            last_name="ManagerFlag",
            is_procurement_manager=True,
        ),
        _get_or_create_user(
            username="procurement_manager_role",
            email="procurement_manager_role@erp.local",
            first_name="Procurement",
            last_name="ManagerRole",
            role=procurement_manager_role,
        ),
    ]

    print("Created or updated the following sample finance/procurement users:")
    for user in users:
        print(f"- {user.username} (role={user.role.slug if user.role else 'none'}, "
              f"finance_manager={user.is_finance_manager}, accountant={user.is_accountant}, "
              f"procurement_officer={user.is_procurement_officer}, procurement_manager={user.is_procurement_manager})")

    return users


def _get_or_create_finance_data(users: list[User]) -> None:
    finance_manager = next((u for u in users if u.is_finance_manager or (u.role and u.role.slug == ROLE_FINANCE_MANAGER)), None)
    accountant = next((u for u in users if u.is_accountant or (u.role and u.role.slug == ROLE_ACCOUNTANT)), None)

    ExpenseCategory.objects.get_or_create(name="Office Supplies")
    ExpenseCategory.objects.get_or_create(name="Travel")
    ExpenseCategory.objects.get_or_create(name="Utilities")

    budget, _ = Budget.objects.get_or_create(
        title="FY 2026 Operations",
        defaults={
            "department": "Finance",
            "fiscal_year": "2026",
            "amount": 120000.00,
            "requested_by": finance_manager,
            "approved": True,
            "approved_by": finance_manager,
            "approved_at": timezone.now(),
            "notes": "Annual operations budget.",
        },
    )

    LedgerAccount.objects.get_or_create(code="1000", defaults={"name": "Cash", "description": "Cash account."})
    LedgerAccount.objects.get_or_create(code="2000", defaults={"name": "Accounts Payable", "description": "Accounts payable."})

    cash_account = LedgerAccount.objects.filter(code="1000").first()
    if cash_account:
        CashBookEntry.objects.get_or_create(
            date=timezone.now().date(),
            reference="CB-001",
            defaults={
                "description": "Petty cash deposit",
                "debit": 5000.00,
                "credit": 0.00,
                "created_by": accountant,
            },
        )

        GeneralLedgerEntry.objects.get_or_create(
            account=cash_account,
            date=timezone.now().date(),
            reference="GL-001",
            defaults={
                "description": "Opening cash balance",
                "debit": 5000.00,
                "credit": 0.00,
                "created_by": accountant,
            },
        )

    bank_reconciliation, _ = BankReconciliation.objects.get_or_create(
        bank_name="First National Bank",
        statement_date=timezone.now().date(),
        defaults={
            "book_balance": 4500.00,
            "bank_balance": 4500.00,
            "reconciled": True,
            "reconciled_at": timezone.now(),
            "reconciled_by": finance_manager,
            "notes": "Monthly reconciliation completed.",
        },
    )

    PaymentVoucher.objects.get_or_create(
        voucher_number="PV-1001",
        defaults={
            "title": "Vendor payment for office supplies",
            "vendor_name": "ABC Supplies Ltd",
            "amount": 1500.00,
            "requested_by": accountant,
            "approved": True,
            "approved_by": finance_manager,
            "approved_at": timezone.now(),
            "status": "approved",
            "notes": "Approved invoice payment.",
        },
    )

    AccountPayable.objects.get_or_create(
        vendor_name="ABC Supplies Ltd",
        defaults={
            "description": "Outstanding office supplies invoice",
            "amount": 1500.00,
            "due_date": timezone.now().date(),
            "paid": False,
            "reference": "INV-2026-0001",
        },
    )

    AccountReceivable.objects.get_or_create(
        customer_name="Alumni Association",
        defaults={
            "description": "Sponsorship payment pending",
            "amount": 2500.00,
            "due_date": timezone.now().date(),
            "received": False,
            "reference": "AR-2026-0001",
        },
    )


def _get_or_create_procurement_data(users: list[User]) -> None:
    procurement_officer = next((u for u in users if u.is_procurement_officer or (u.role and u.role.slug == ROLE_PROCUREMENT_OFFICER)), None)
    procurement_manager = next((u for u in users if u.is_procurement_manager or (u.role and u.role.slug == ROLE_PROCUREMENT_MANAGER)), None)

    supplier_category, _ = SupplierCategory.objects.get_or_create(
        name="Stationery",
        defaults={"description": "Office stationery and consumables."},
    )

    tech_category, _ = SupplierCategory.objects.get_or_create(
        name="IT Supplies",
        defaults={"description": "Technology equipment and computer accessories."},
    )

    supplier, _ = Supplier.objects.get_or_create(
        name="Office Essentials Ltd",
        defaults={
            "category": supplier_category,
            "email": "sales@officeessentials.local",
            "phone": "+1234567890",
            "address": "123 Procurement Street",
            "is_blacklisted": False,
            "created_by": procurement_officer,
        },
    )

    tech_supplier, _ = Supplier.objects.get_or_create(
        name="Local Tech Supplies",
        defaults={
            "category": tech_category,
            "email": "procure@localtech.local",
            "phone": "+1234567899",
            "address": "45 Technology Ave",
            "is_blacklisted": False,
            "created_by": procurement_manager,
        },
    )

    procurement_department, _ = ProcurementDepartment.objects.get_or_create(
        slug="procurement",
        defaults={"name": "Procurement"},
    )
    admin_department, _ = ProcurementDepartment.objects.get_or_create(
        slug="administration",
        defaults={"name": "Administration"},
    )

    statuses = {
        'draft': ProcurementStatus.objects.get_or_create(
            slug='draft',
            defaults={'name': 'Draft', 'is_default': True},
        )[0],
        'submitted': ProcurementStatus.objects.get_or_create(
            slug='submitted',
            defaults={'name': 'Submitted', 'is_default': False},
        )[0],
        'pending_approval': ProcurementStatus.objects.get_or_create(
            slug='pending_approval',
            defaults={'name': 'Pending Approval', 'is_default': False},
        )[0],
        'approved': ProcurementStatus.objects.get_or_create(
            slug='approved',
            defaults={'name': 'Approved', 'is_default': False},
        )[0],
        'rejected': ProcurementStatus.objects.get_or_create(
            slug='rejected',
            defaults={'name': 'Rejected', 'is_default': False},
        )[0],
    }

    plan, _ = ProcurementPlan.objects.get_or_create(
        title="Stationery Procurement FY 2026",
        defaults={
            "department": procurement_department,
            "fiscal_year": "2026",
            "requested_by": procurement_officer,
            "approved": True,
            "approved_at": timezone.now(),
        },
    )

    requisition, _ = PurchaseRequisition.objects.get_or_create(
        title="Office stationery replenishment",
        defaults={
            "description": "Request for new stationery and printer supplies.",
            "department": admin_department,
            "requested_by": procurement_officer,
            "status": statuses['submitted'],
            "total_amount": 2200.00,
            "required_by": timezone.now().date(),
        },
    )

    office_requisition, _ = PurchaseRequisition.objects.get_or_create(
        title="IT accessories replacement",
        defaults={
            "description": "Request for new keyboards, mice, and laptop accessories.",
            "department": procurement_department,
            "requested_by": procurement_manager,
            "status": statuses['pending_approval'],
            "total_amount": 4100.00,
            "required_by": timezone.now().date(),
        },
    )

    PurchaseOrder.objects.get_or_create(
        supplier=supplier,
        requisition=requisition,
        defaults={
            "total_amount": 2200.00,
            "approved": True,
            "approved_at": timezone.now(),
        },
    )

    PurchaseOrder.objects.get_or_create(
        supplier=tech_supplier,
        requisition=office_requisition,
        defaults={
            "total_amount": 4100.00,
            "approved": False,
        },
    )


def generate_finance_and_procurement_data() -> list[User]:
    users = generate_finance_and_procurement_users()
    _get_or_create_finance_data(users)
    _get_or_create_procurement_data(users)
    print("Sample finance and procurement data created.")
    return users


def run(*args: Any) -> None:
    """Entry point for django-extensions runscript."""
    generate_finance_and_procurement_data()


if __name__ == "__main__":
    generate_finance_and_procurement_data()

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ModulePermission, Permission, Role, RolePermission, UserPermission
from accounts.views_api import RoleViewSet
from accounts.permissions import (
    IsAccountant,
    IsFinanceManager,
    IsProcurementManager,
    IsProcurementOfficer,
    IsSuperAdministrator,
)

User = get_user_model()


class AccountPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.finance_manager_flag = User.objects.create_user(
            username="finance_manager_flag",
            email="finance_manager_flag@example.com",
            password="pass1234",
            is_finance=True,
            is_finance_manager=True,
        )
        self.finance_manager_role = User.objects.create_user(
            username="finance_manager_role",
            email="finance_manager_role@example.com",
            password="pass1234",
        )
        self.finance_manager_role.role = Role.objects.create(
            name="Finance Manager",
            slug="finance_manager",
        )
        self.finance_manager_role.save()

        self.accountant_flag = User.objects.create_user(
            username="accountant_flag",
            email="accountant_flag@example.com",
            password="pass1234",
            is_finance=True,
            is_accountant=True,
        )
        self.accountant_role = User.objects.create_user(
            username="accountant_role",
            email="accountant_role@example.com",
            password="pass1234",
        )
        self.accountant_role.role = Role.objects.create(
            name="Accountant",
            slug="accountant",
        )
        self.accountant_role.save()

        self.procurement_officer_flag = User.objects.create_user(
            username="procurement_officer_flag",
            email="procurement_officer_flag@example.com",
            password="pass1234",
            is_procurement_officer=True,
        )
        self.procurement_officer_role = User.objects.create_user(
            username="procurement_officer_role",
            email="procurement_officer_role@example.com",
            password="pass1234",
        )
        self.procurement_officer_role.role = Role.objects.create(
            name="Procurement Officer",
            slug="procurement_officer",
        )
        self.procurement_officer_role.save()

        self.procurement_manager_flag = User.objects.create_user(
            username="procurement_manager_flag",
            email="procurement_manager_flag@example.com",
            password="pass1234",
            is_procurement_manager=True,
        )
        self.procurement_manager_role = User.objects.create_user(
            username="procurement_manager_role",
            email="procurement_manager_role@example.com",
            password="pass1234",
        )
        self.procurement_manager_role.role = Role.objects.create(
            name="Procurement Manager",
            slug="procurement_manager",
        )
        self.procurement_manager_role.save()

        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="regular_user@example.com",
            password="pass1234",
        )

    def _make_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_finance_manager_permission_with_flag(self):
        permission = IsFinanceManager()
        self.assertTrue(permission.has_permission(self._make_request(self.finance_manager_flag), None))

    def test_finance_manager_permission_with_role(self):
        permission = IsFinanceManager()
        self.assertTrue(permission.has_permission(self._make_request(self.finance_manager_role), None))

    def test_accountant_permission_with_flag(self):
        permission = IsAccountant()
        self.assertTrue(permission.has_permission(self._make_request(self.accountant_flag), None))

    def test_accountant_permission_with_role(self):
        permission = IsAccountant()
        self.assertTrue(permission.has_permission(self._make_request(self.accountant_role), None))

    def test_procurement_officer_permission_with_flag(self):
        permission = IsProcurementOfficer()
        self.assertTrue(permission.has_permission(self._make_request(self.procurement_officer_flag), None))

    def test_procurement_officer_permission_with_role(self):
        permission = IsProcurementOfficer()
        self.assertTrue(permission.has_permission(self._make_request(self.procurement_officer_role), None))

    def test_procurement_manager_permission_with_flag(self):
        permission = IsProcurementManager()
        self.assertTrue(permission.has_permission(self._make_request(self.procurement_manager_flag), None))

    def test_procurement_manager_permission_with_role(self):
        permission = IsProcurementManager()
        self.assertTrue(permission.has_permission(self._make_request(self.procurement_manager_role), None))

    def test_finance_manager_permission_denies_regular_user(self):
        permission = IsFinanceManager()
        self.assertFalse(permission.has_permission(self._make_request(self.regular_user), None))

    def test_accountant_permission_denies_regular_user(self):
        permission = IsAccountant()
        self.assertFalse(permission.has_permission(self._make_request(self.regular_user), None))

    def test_procurement_officer_permission_denies_regular_user(self):
        permission = IsProcurementOfficer()
        self.assertFalse(permission.has_permission(self._make_request(self.regular_user), None))

    def test_procurement_manager_permission_denies_regular_user(self):
        permission = IsProcurementManager()
        self.assertFalse(permission.has_permission(self._make_request(self.regular_user), None))

    def test_user_permission_deny_overrides_role_and_legacy_module_grants(self):
        permission = Permission.objects.create(
            name="Edit procurement plans",
            code="procurement_plans_edit",
        )
        role = Role.objects.create(name="Procurement Editor", slug="procurement_editor")
        RolePermission.objects.create(role=role, permission=permission)
        self.regular_user.role = role
        self.regular_user.save(update_fields=["role"])
        ModulePermission.objects.create(
            user=self.regular_user,
            module_name="procurement_plans_edit",
        )
        UserPermission.objects.create(
            user=self.regular_user,
            permission=permission,
            effect=UserPermission.DENY,
        )

        self.assertFalse(self.regular_user.has_permission("procurement_plans_edit"))
        self.assertFalse(self.regular_user.can_access_module("procurement_plans"))

    def test_account_management_api_permission_requires_superuser(self):
        permission = IsSuperAdministrator()
        superuser = User.objects.create_superuser(
            username="api_admin",
            email="api_admin@example.com",
            password="test-password",
        )

        self.assertFalse(permission.has_permission(self._make_request(self.regular_user), None))
        self.assertTrue(permission.has_permission(self._make_request(superuser), None))

    def test_role_api_rejects_regular_users_and_allows_superusers(self):
        factory = APIRequestFactory()
        role_list = RoleViewSet.as_view({"get": "list"})

        request = factory.get("/api/roles/")
        force_authenticate(request, user=self.regular_user)
        self.assertEqual(role_list(request).status_code, 403)

        superuser = User.objects.create_superuser(
            username="role_api_admin",
            email="role_api_admin@example.com",
            password="test-password",
        )
        request = factory.get("/api/roles/")
        force_authenticate(request, user=superuser)
        self.assertEqual(role_list(request).status_code, 200)

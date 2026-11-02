from rest_framework.permissions import BasePermission


class IsSuperAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_superuser
        )


class IsFinanceManager(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_finance_manager
                or request.user.has_role("finance_manager")
            )
        )


class IsAccountant(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (request.user.is_accountant or request.user.has_role("accountant"))
        )


class IsProcurementOfficer(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_procurement_officer
                or request.user.has_role("procurement_officer")
            )
        )


class IsProcurementManager(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_procurement_manager
                or request.user.has_role("procurement_manager")
            )
        )

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Permission, Role, RolePermission, User, UserPermission
from audit.models import ActivityLog


@override_settings(LANGUAGE_CODE="en")
class AccessControlAdministrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="access-admin",
            email="access-admin@example.test",
            password="test-password",
        )
        self.user = User.objects.create_user(
            username="override-user",
            password="test-password",
        )
        self.permission = Permission.objects.create(
            name="View example report",
            code="example.report_view",
        )
        self.role = Role.objects.create(
            name="Report Viewer",
            slug="report-viewer",
        )
        self.role_permission = RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
        )

    def test_admin_can_create_audited_user_deny_override(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("user_permission_add"),
            {
                "user": self.user.pk,
                "permission": self.permission.pk,
                "effect": UserPermission.DENY,
                "reason": "Temporary access restriction",
            },
        )

        self.assertRedirects(response, reverse("user_permission_list"))
        override = UserPermission.objects.get(user=self.user)
        self.assertEqual(override.created_by, self.admin)
        self.assertFalse(self.user.has_permission("example.report_view"))
        event = ActivityLog.objects.get(action="rbac.user_permission.deny")
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.target_model, "accounts.UserPermission")
        self.assertEqual(event.after["reason"], "Temporary access restriction")

    def test_override_list_is_protected_and_override_revocation_is_post_only(self):
        override = UserPermission.objects.create(
            user=self.user,
            permission=self.permission,
            effect=UserPermission.DENY,
            created_by=self.admin,
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("user_permission_list")).status_code, 302)

        self.client.force_login(self.admin)
        delete_url = reverse("user_permission_delete", args=(override.pk,))
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse("user_permission_list"))
        self.assertFalse(UserPermission.objects.filter(pk=override.pk).exists())
        event = ActivityLog.objects.get(action="rbac.user_permission.revoked")
        self.assertEqual(event.before["effect"], UserPermission.DENY)

    def test_role_permission_removal_is_post_only_and_audited(self):
        self.client.force_login(self.admin)
        delete_url = reverse(
            "role_permission_delete",
            args=(self.role_permission.pk,),
        )

        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse("role_permission_list"))
        self.assertFalse(
            RolePermission.objects.filter(pk=self.role_permission.pk).exists()
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                action="rbac.role_permission.revoked",
            ).exists()
        )

    def test_role_and_permission_removal_reject_get_requests(self):
        self.client.force_login(self.admin)

        self.assertEqual(
            self.client.get(
                reverse("role_delete", args=(self.role.pk,))
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(
                reverse("permission_delete", args=(self.permission.pk,))
            ).status_code,
            405,
        )

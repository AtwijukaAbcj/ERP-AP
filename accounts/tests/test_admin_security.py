from unittest.mock import patch

from django import forms
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import (
    ACTIVE_MODULE_CHOICES,
    ModulePermission,
    Permission,
    Role,
    RolePermission,
    Student,
    User,
    UserPermission,
)
from accounts.forms import RolePermissionForm, UserAddForm, UserRolesForm
from audit.models import ActivityLog
from finance.models import FinanceModulePermission as FinanceAppModulePermission
from finance.permissions import has_finance_permission


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

    @patch("accounts.forms.send_new_account_email")
    def test_new_user_account_gets_generated_password_and_email(self, send_email):
        role = Role.objects.create(name="General Staff", slug="general-staff")
        form = UserAddForm(
            data={
                "username": "base-account",
                "first_name": "Base",
                "last_name": "Account",
                "email": "base-account@example.test",
                "gender": "M",
                "address": "Campus",
                "phone": "123456789",
                "roles": [role.pk],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.role, role)
        self.assertEqual(list(user.roles.all()), [role])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_student)
        self.assertFalse(user.is_lecturer)
        self.assertFalse(user.is_finance)
        self.assertFalse(user.is_registrar)
        self.assertNotIn("password1", form.fields)
        self.assertNotIn("password2", form.fields)
        self.assertTrue(user.check_password(form.generated_password))
        send_email.assert_called_once_with(user, form.generated_password)

    def test_user_creation_accepts_roles_without_setting_account_type_flags(self):
        role = Role.objects.create(name="Finance Reviewer", slug="finance-reviewer")
        form = UserAddForm(
            data={
                "username": "role-based-user",
                "first_name": "Role",
                "last_name": "Based",
                "email": "role-based@example.test",
                "gender": "M",
                "address": "Campus",
                "phone": "123456789",
                "roles": [role.pk],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.roles.get(), role)
        self.assertEqual(user.role, role)
        self.assertFalse(user.is_student)
        self.assertFalse(user.is_lecturer)
        self.assertFalse(user.is_finance)
        self.assertFalse(user.is_registrar)
        self.assertFalse(Student.objects.filter(student=user).exists())

    def test_admin_can_assign_multiple_roles_to_an_existing_user(self):
        second_permission = Permission.objects.create(
            name="View another report",
            code="example.other_report_view",
        )
        second_role = Role.objects.create(name="Other Viewer", slug="other-viewer")
        RolePermission.objects.create(
            role=second_role,
            permission=second_permission,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("user_roles", args=(self.user.pk,)),
            {"roles": [self.role.pk, second_role.pk]},
        )

        self.assertRedirects(response, reverse("user_list"))
        self.user.refresh_from_db()
        self.assertSetEqual(
            set(self.user.roles.values_list("pk", flat=True)),
            {self.role.pk, second_role.pk},
        )
        self.assertTrue(self.user.has_permission("example.report_view"))
        self.assertTrue(self.user.has_permission("example.other_report_view"))
        self.assertTrue(self.user.has_role("report-viewer"))
        self.assertTrue(self.user.has_role("other-viewer"))
        event = ActivityLog.objects.get(action="rbac.user_roles.updated")
        self.assertEqual(event.user, self.admin)
        self.assertEqual(
            set(event.after["roles"]),
            {"Other Viewer", "Report Viewer"},
        )

    def test_user_roles_form_shows_all_roles_as_visible_checkboxes(self):
        second_role = Role.objects.create(name="Other Viewer", slug="other-viewer")
        form = UserRolesForm(instance=self.user)

        self.assertIsInstance(
            form.fields["roles"].widget,
            forms.CheckboxSelectMultiple,
        )
        self.assertEqual(
            set(form.fields["roles"].queryset.values_list("pk", flat=True)),
            {self.role.pk, second_role.pk},
        )

    def test_non_admin_cannot_assign_roles(self):
        response = self.client.post(
            reverse("user_roles", args=(self.user.pk,)),
            {"roles": [self.role.pk]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.user.roles.exists())

    def test_lecturer_profile_links_to_existing_edit_view(self):
        lecturer = User.objects.create_user(
            username="profile-lecturer",
            password="test-password",
            is_lecturer=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("profile_single", args=(lecturer.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("staff_edit", kwargs={"pk": lecturer.pk}),
        )

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

    def test_role_permission_form_uses_role_radio_and_permission_checkboxes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("role_permission_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, "Choose a role")
        self.assertContains(response, "Choose permissions")
        self.assertIsInstance(response.context["form"].fields["role"].widget, forms.RadioSelect)
        self.assertIsInstance(
            response.context["form"].fields["permissions"].widget,
            forms.CheckboxSelectMultiple,
        )
        self.assertNotIn(
            "Other",
            [
                group_label
                for group_label, _options in response.context["form"].fields[
                    "permissions"
                ].choices
            ],
        )

    def test_role_permission_form_assigns_multiple_permissions_without_duplicate_grants(self):
        additional_permission = Permission.objects.create(
            name="Export example report",
            code="example.report_export",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("role_permission_add"),
            {
                "role": self.role.pk,
                "permissions": [self.permission.pk, additional_permission.pk],
            },
        )

        self.assertRedirects(response, reverse("role_permission_list"))
        self.assertEqual(
            RolePermission.objects.filter(role=self.role).count(),
            2,
        )
        self.assertEqual(
            ActivityLog.objects.filter(
                action="rbac.role_permission.granted",
                after__permission=additional_permission.code,
            ).count(),
            1,
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

    def test_module_assignment_is_admin_only_replaceable_and_revoke_is_post_only(self):
        assign_url = reverse("assign_modules")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(assign_url).status_code, 302)
        self.assertEqual(
            self.client.post(
                assign_url,
                {"user": self.user.pk, "modules": ["procurement_dashboard"]},
            ).status_code,
            302,
        )
        self.assertFalse(ModulePermission.objects.filter(user=self.user).exists())

        self.client.force_login(self.admin)
        response = self.client.post(
            assign_url,
            {
                "user": self.user.pk,
                "modules": ["procurement_dashboard", "procurement_orders"],
            },
        )
        self.assertRedirects(response, assign_url)
        self.assertSetEqual(
            set(
                ModulePermission.objects.filter(user=self.user).values_list(
                    "module_name", flat=True
                )
            ),
            {"procurement_dashboard", "procurement_orders"},
        )
        response = self.client.get(f"{assign_url}?user_id={self.user.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            set(response.context["form"]["modules"].value()),
            {"procurement_dashboard", "procurement_orders"},
        )

        response = self.client.post(
            assign_url,
            {"user": self.user.pk, "modules": ["procurement_dashboard"]},
        )
        self.assertRedirects(response, assign_url)
        self.assertSetEqual(
            set(
                ModulePermission.objects.filter(user=self.user).values_list(
                    "module_name", flat=True
                )
            ),
            {"procurement_dashboard"},
        )

        response = self.client.post(assign_url, {"user": self.user.pk})
        self.assertRedirects(response, assign_url)
        self.assertFalse(ModulePermission.objects.filter(user=self.user).exists())
        response = self.client.post(
            assign_url,
            {"user": self.user.pk, "modules": ["procurement_dashboard"]},
        )
        self.assertRedirects(response, assign_url)

        permission = ModulePermission.objects.get(
            user=self.user,
            module_name="procurement_dashboard",
        )
        delete_url = reverse("delete_module_permission", args=(permission.pk,))
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertRedirects(self.client.post(delete_url), assign_url)
        self.assertFalse(ModulePermission.objects.filter(user=self.user).exists())

    def test_module_assignment_page_renders_searchable_access_catalog(self):
        ModulePermission.objects.create(
            user=self.user,
            module_name="procurement_dashboard",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("assign_modules"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User module access")
        self.assertContains(response, "Find a module")
        self.assertContains(response, "Select visible")
        self.assertContains(response, "Academic Programs & Courses")
        self.assertContains(response, "Assessments & Results")
        self.assertContains(response, "module-access-category-options")
        self.assertContains(response, "module-access-actions")
        self.assertContains(response, "Explicit denies continue to take precedence.")
        self.assertContains(response, "module-access.css")

    def test_lecturer_module_grant_shows_read_only_directory_access(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("lecturer_list"))

        self.assertEqual(response.status_code, 200)
        sidebar_menu = response.content.decode().split(
            '<nav class="sidebar-menu">',
            maxsplit=1,
        )[1].split("</nav>", maxsplit=1)[0]
        self.assertIn("Lecturers", sidebar_menu)
        self.assertIn(f'href="{reverse("lecturer_list")}"', sidebar_menu)
        self.assertIn(f'href="{reverse("add_lecturer")}"', sidebar_menu)
        self.assertIn("Users", sidebar_menu)
        self.assertIn(f'href="{reverse("user_list")}"', sidebar_menu)
        self.assertIn(f'href="{reverse("user_add")}"', sidebar_menu)

        ModulePermission.objects.create(
            user=self.user,
            module_name="lecturers",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("lecturer_list"))
        self.assertEqual(response.status_code, 200)
        sidebar_menu = response.content.decode().split(
            '<nav class="sidebar-menu">',
            maxsplit=1,
        )[1].split("</nav>", maxsplit=1)[0]
        self.assertIn("Lecturer Directory", sidebar_menu)
        self.assertIn(f'href="{reverse("lecturer_list")}"', sidebar_menu)
        self.assertNotIn("Add Lecturer", sidebar_menu)
        self.assertNotIn(reverse("add_lecturer"), sidebar_menu)
        self.assertNotIn("User Directory", sidebar_menu)
        self.assertNotIn(reverse("user_list"), sidebar_menu)

    def test_assigned_module_catalog_is_visible_and_usable_from_sidebar(self):
        ModulePermission.objects.bulk_create(
            ModulePermission(user=self.user, module_name=module_name)
            for module_name, _label in ACTIVE_MODULE_CHOICES
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        sidebar_menu = response.content.decode().split(
            '<nav class="sidebar-menu">',
            maxsplit=1,
        )[1].split("</nav>", maxsplit=1)[0]
        visible_destinations = (
            "lecturer_list",
            "session_list",
            "semester_list",
            "manage_faculties",
            "student_list",
            "finance:invoice_list",
            "procurement:dashboard",
            "admissions:dashboard",
            "clinical:placement_list",
            "assessment_hub",
            "quiz_marking",
            "quiz_progress",
            "voting_home",
            "faculty_audit_logs",
            "institutional_reports",
        )
        for destination in visible_destinations:
            with self.subTest(destination=destination):
                self.assertIn(reverse(destination), sidebar_menu)

        self.assertNotIn(reverse("user_list"), sidebar_menu)
        self.assertNotIn(reverse("assign_modules"), sidebar_menu)
        self.assertNotIn(reverse("admin_panel"), sidebar_menu)
        self.assertNotIn(reverse("add_lecturer"), sidebar_menu)

        accessible_destinations = (
            "lecturer_list",
            "session_list",
            "semester_list",
            "manage_faculties",
            "voting_home",
            "quiz_marking",
            "voting_home",
            "faculty_audit_logs",
            "institutional_reports",
        )
        for destination in accessible_destinations:
            with self.subTest(destination=destination):
                self.assertEqual(
                    self.client.get(reverse(destination)).status_code,
                    200,
                )

    def test_assignment_module_grant_opens_course_catalog_only(self):
        ModulePermission.objects.create(
            user=self.user,
            module_name="assignments.view",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        sidebar_menu = response.content.decode().split(
            '<nav class="sidebar-menu">',
            maxsplit=1,
        )[1].split("</nav>", maxsplit=1)[0]
        self.assertIn(reverse("programs"), sidebar_menu)
        self.assertNotIn(reverse("course_allocation_view"), sidebar_menu)
        self.assertNotIn(reverse("course_allocation"), sidebar_menu)
        self.assertEqual(self.client.get(reverse("programs")).status_code, 200)

    def test_role_granted_finance_and_procurement_modules_appear_in_sidebar(self):
        role = Role.objects.create(name="Finance and Procurement User", slug="finance-procurement-user")
        for code, name in (
            ("finance", "Finance"),
            ("procurement_dashboard", "Procurement Dashboard"),
        ):
            permission = Permission.objects.get_or_create(
                code=code,
                defaults={"name": name},
            )[0]
            RolePermission.objects.create(role=role, permission=permission)
        self.user.roles.add(role)
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("finance:invoice_list"))
        self.assertContains(response, reverse("procurement:dashboard"))
        self.assertNotContains(response, reverse("user_list"))

    def test_procurement_actions_are_available_for_role_assignment(self):
        permission = Permission.objects.get(code="procurement_plans_approve")
        role = Role.objects.create(name="Plan Approver", slug="plan-approver")
        RolePermission.objects.create(role=role, permission=permission)
        self.user.role = role
        self.user.save(update_fields=("role",))

        self.assertTrue(self.user.has_permission("procurement_plans_approve"))

    def test_finance_module_assignment_is_admin_only_and_revocation_is_post_only(self):
        finance_user = User.objects.create_user(
            username="finance-module-user",
            email="finance-module-user@example.test",
            is_finance=True,
        )
        assignment = FinanceAppModulePermission.objects.create(
            staff=finance_user,
            module_name="manage_invoices",
        )
        assign_url = reverse("finance:assign_finance_modules")
        revoke_url = reverse("finance:revoke_finance_module", args=(assignment.pk,))

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(assign_url).status_code, 302)
        self.assertEqual(self.client.post(revoke_url).status_code, 302)
        self.assertTrue(FinanceAppModulePermission.objects.filter(pk=assignment.pk).exists())

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(revoke_url).status_code, 405)
        response = self.client.post(revoke_url)

        self.assertRedirects(response, assign_url)
        self.assertFalse(FinanceAppModulePermission.objects.filter(pk=assignment.pk).exists())

    def test_module_level_finance_grant_is_overridden_by_an_action_deny(self):
        ModulePermission.objects.create(user=self.user, module_name="finance")
        self.assertTrue(has_finance_permission(self.user, "manage_invoices"))

        permission = Permission.objects.get(code="manage_invoices")
        UserPermission.objects.create(
            user=self.user,
            permission=permission,
            effect=UserPermission.DENY,
        )
        self.assertFalse(has_finance_permission(self.user, "manage_invoices"))

    def test_application_module_access_is_required_and_user_denies_override_module_grants(self):
        voting_url = reverse("voting_home")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(voting_url).status_code, 403)

        ModulePermission.objects.create(user=self.user, module_name="voting")
        self.assertEqual(self.client.get(voting_url).status_code, 200)

        voting_permission = Permission.objects.get(code="voting")
        UserPermission.objects.create(
            user=self.user,
            permission=voting_permission,
            effect=UserPermission.DENY,
        )
        self.assertEqual(self.client.get(voting_url).status_code, 403)

    def test_admin_can_reset_another_users_password_and_audit_it(self):
        self.user.set_password("old-test-password-2026")
        self.user.save(update_fields=("password",))
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("user_password_reset", args=(self.user.pk,)),
            {
                "new_password1": "New-secure-test-password-2026!",
                "new_password2": "New-secure-test-password-2026!",
            },
        )

        self.assertRedirects(response, reverse("user_list"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-secure-test-password-2026!"))
        self.assertFalse(self.user.check_password("old-test-password-2026"))
        event = ActivityLog.objects.get(action="user.password_reset")
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.target_model, "accounts.User")
        self.assertEqual(event.object_id, str(self.user.pk))
        self.assertNotIn(
            "New-secure-test-password-2026!",
            event.description,
        )

    def test_password_reset_is_restricted_to_admins(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("user_password_reset", args=(self.user.pk,))
        )

        self.assertRedirects(
            response,
            reverse("permission_denied"),
            fetch_redirect_response=False,
        )

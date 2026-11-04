from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from accounts.views import EMAIL_TEMPLATE_CATALOG


@override_settings(LANGUAGE_CODE="en")
class EmailTemplateAdministrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="template-admin",
            email="admin@example.test",
            password="Strong-test-password-2026!",
        )
        self.user = User.objects.create_user(
            username="template-user",
            email="user@example.test",
            password="Strong-test-password-2026!",
        )

    def test_superuser_can_open_email_template_directory_from_sidebar(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("email_template_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email Templates")
        self.assertContains(response, reverse("email_template_preview", args=("student",)))
        self.assertContains(response, "General user account")

    def test_superuser_can_preview_each_account_email_template(self):
        self.client.force_login(self.admin)

        for email_template in EMAIL_TEMPLATE_CATALOG:
            with self.subTest(template=email_template["key"]):
                response = self.client.get(
                    reverse(
                        "email_template_preview",
                        args=(email_template["key"],),
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "View template HTML")
                self.assertContains(
                    response,
                    reverse(
                        "email_template_render",
                        args=(email_template["key"],),
                    ),
                )

                rendered_email = self.client.get(
                    reverse(
                        "email_template_render",
                        args=(email_template["key"],),
                    )
                )
                self.assertEqual(rendered_email.status_code, 200)
                self.assertEqual(
                    rendered_email["X-Frame-Options"],
                    "SAMEORIGIN",
                )
                self.assertContains(rendered_email, "Example-Password-123")
                self.assertContains(rendered_email, "Jordan Example")

    def test_non_admin_cannot_access_email_templates(self):
        self.client.force_login(self.user)

        for url in (
            reverse("email_template_list"),
            reverse("email_template_edit", args=("general-user",)),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertRedirects(response, reverse("permission_denied"))

    def test_admin_can_save_valid_template_and_see_it_in_preview(self):
        self.client.force_login(self.admin)
        template_key = "test-template"
        with TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "email.html"
            template_path.write_text("<p>Before</p>", encoding="utf-8")
            catalog = (
                {
                    "key": template_key,
                    "title": "Test email",
                    "template": "accounts/email/test.html",
                    "description": "Test template",
                },
            )
            with (
                patch("accounts.views.EMAIL_TEMPLATE_CATALOG", catalog),
                patch(
                    "accounts.views.get_template",
                    return_value=SimpleNamespace(
                        origin=SimpleNamespace(name=str(template_path))
                    ),
                ),
            ):
                edit_url = reverse("email_template_edit", args=(template_key,))
                response = self.client.get(edit_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["form"].initial["source"],
                    "<p>Before</p>",
                )

                response = self.client.post(
                    edit_url,
                    {"source": "<p>Updated {{ user.get_full_name }}</p>"},
                )

                self.assertRedirects(
                    response,
                    reverse("email_template_preview", args=(template_key,)),
                    fetch_redirect_response=False,
                )
                self.assertEqual(
                    template_path.read_text(encoding="utf-8"),
                    "<p>Updated {{ user.get_full_name }}</p>",
                )

    def test_invalid_template_syntax_is_rejected_without_overwriting_file(self):
        self.client.force_login(self.admin)
        template_key = "test-template"
        with TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "email.html"
            original_source = "<p>Keep this template</p>"
            template_path.write_text(original_source, encoding="utf-8")
            catalog = (
                {
                    "key": template_key,
                    "title": "Test email",
                    "template": "accounts/email/test.html",
                    "description": "Test template",
                },
            )
            with (
                patch("accounts.views.EMAIL_TEMPLATE_CATALOG", catalog),
                patch(
                    "accounts.views.get_template",
                    return_value=SimpleNamespace(
                        origin=SimpleNamespace(name=str(template_path))
                    ),
                ),
            ):
                response = self.client.post(
                    reverse("email_template_edit", args=(template_key,)),
                    {"source": "{% if user %}Missing endif"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Invalid Django template syntax")
                self.assertEqual(
                    template_path.read_text(encoding="utf-8"),
                    original_source,
                )

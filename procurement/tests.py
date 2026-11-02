import csv
from io import BytesIO, StringIO
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient

from accounts.models import ModulePermission, Permission, Role, User, UserPermission

from .serializers import PurchaseOrderSerializer
from .models import (
    ProcurementPlan,
    ProcurementStatus,
    ProcurementDepartment,
    ProcurementWorkflowRule,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseRequisition,
    Supplier,
)


@override_settings(LANGUAGE_CODE="en")
class ProcurementWorkflowTests(TestCase):
    def setUp(self):
        self.officer = User.objects.create_user(
            username="procurement-officer",
            password="test-password",
            is_procurement_officer=True,
        )
        self.manager = User.objects.create_user(
            username="procurement-manager",
            password="test-password",
            is_procurement_manager=True,
        )
        self.superuser = User.objects.create_superuser(
            username="procurement-admin",
            password="test-password",
        )
        self.supplier = Supplier.objects.create(name="Approved supplier")
        self.pending_status = ProcurementStatus.objects.get(slug="pending_approval")
        self.approved_status = ProcurementStatus.objects.get(slug="approved")
        self.requisition = PurchaseRequisition.objects.create(
            title="Ward equipment",
            status=self.pending_status,
            total_amount=Decimal("500.00"),
        )

    def create_quotation(
        self,
        requisition=None,
        supplier=None,
        total=Decimal("250.00"),
        status=PurchaseQuotation.Status.ACCEPTED,
        description="Examination couch",
        quantity=2,
        unit_price=Decimal("125.00"),
    ):
        quotation = PurchaseQuotation.objects.create(
            supplier=supplier or self.supplier,
            requisition=requisition or self.requisition,
            status=status,
            total_amount=total,
            document="test-supplier-quotation.pdf",
        )
        PurchaseQuotationItem.objects.create(
            quotation=quotation,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
        )
        return quotation

    def test_requisition_approval_requires_post_and_manager(self):
        approval_url = reverse(
            "procurement:purchase_requisition_approve",
            args=(self.requisition.pk,),
        )
        self.client.force_login(self.officer)

        self.assertEqual(self.client.get(approval_url).status_code, 405)
        response = self.client.post(approval_url)
        self.assertEqual(response.status_code, 403)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status.slug, "pending_approval")

        self.client.force_login(self.manager)
        response = self.client.post(approval_url, {"comment": "Approved for purchase."})
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status.slug, "approved")

    def test_procurement_module_assignment_controls_dashboard_access(self):
        dashboard_url = reverse("procurement:dashboard")
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(dashboard_url).status_code, 403)

        ModulePermission.objects.create(
            user=self.officer,
            module_name="procurement_dashboard",
        )
        self.assertEqual(self.client.get(dashboard_url).status_code, 200)

        ModulePermission.objects.filter(
            user=self.officer,
            module_name="procurement_dashboard",
        ).delete()
        ModulePermission.objects.create(
            user=self.officer,
            module_name="procurement",
        )
        self.assertEqual(self.client.get(dashboard_url).status_code, 200)

        permission = Permission.objects.get(code="procurement_dashboard")
        UserPermission.objects.create(
            user=self.officer,
            permission=permission,
            effect=UserPermission.DENY,
        )
        self.assertEqual(self.client.get(dashboard_url).status_code, 403)

    def test_procurement_sidebar_exposes_quotation_and_configuration_workflows(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("procurement:dashboard"))

        self.assertEqual(response.status_code, 200)
        for route_name in (
            "purchase_quotation_list",
            "procurement_department_list",
            "procurement_status_list",
        ):
            with self.subTest(route=route_name):
                self.assertContains(
                    response,
                    reverse(f"procurement:{route_name}"),
                )
        self.assertContains(response, "Supplier Quotations")
        self.assertContains(response, "Statuses &amp; Workflow")

    def test_explicit_procurement_deny_overrides_manager_access(self):
        permission = Permission.objects.get(code="procurement_dashboard")
        UserPermission.objects.create(
            user=self.manager,
            permission=permission,
            effect=UserPermission.DENY,
        )
        self.client.force_login(self.manager)

        self.assertEqual(
            self.client.get(reverse("procurement:dashboard")).status_code,
            403,
        )

    def test_requisition_review_requires_a_reason(self):
        self.client.force_login(self.manager)
        transition_url = reverse(
            "procurement:purchase_requisition_transition",
            args=(self.requisition.pk,),
        )
        response = self.client.post(transition_url, {"action": "approve"})
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status.slug, "pending_approval")

        response = self.client.post(
            transition_url,
            {"action": "approve", "comment": "Approved for the department."},
        )
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status.slug, "approved")
        self.assertTrue(
            self.requisition.status_history.filter(
                to_status="approved",
                comment="Approved for the department.",
            ).exists()
        )

    def test_requisition_actions_use_a_three_dot_menu_and_reason_dialog(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("procurement:purchase_requisition_list")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fa-ellipsis-v")
        self.assertContains(response, 'data-bs-display="static"')
        self.assertContains(response, 'id="requisitionActionModal"')
        self.assertContains(response, 'data-action="rule:')
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, "document.body.appendChild(menu)")
        self.assertContains(response, "shown.bs.dropdown")

    def test_department_workflow_routes_through_named_approver_then_manager(self):
        department = ProcurementDepartment.objects.create(
            name="Nursing",
            slug="nursing",
        )
        department_review = ProcurementStatus.objects.create(
            name="Department Review",
            slug="department_review",
        )
        head = User.objects.create_user(
            username="nursing-head",
            password="test-password",
        )
        self.requisition.department = department
        self.requisition.requested_by = self.officer
        self.requisition.save()
        department_rule = ProcurementWorkflowRule.objects.create(
            from_status=self.pending_status,
            to_status=department_review,
            department=department,
            action_label="Department review",
            approver_type=ProcurementWorkflowRule.ApproverType.USER,
            approver_user=head,
        )
        manager_rule = ProcurementWorkflowRule.objects.create(
            from_status=department_review,
            to_status=self.approved_status,
            department=department,
            action_label="Approve after department review",
            approver_type=ProcurementWorkflowRule.ApproverType.USER,
            approver_user=self.manager,
        )
        url = reverse(
            "procurement:purchase_requisition_transition",
            args=(self.requisition.pk,),
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            url,
            {"action": f"rule:{department_rule.pk}", "comment": "Department review."},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(head)
        response = self.client.post(
            url,
            {"action": f"rule:{department_rule.pk}", "comment": "Department review."},
        )
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, department_review)

        self.client.force_login(self.manager)
        response = self.client.post(
            url,
            {
                "action": f"rule:{manager_rule.pk}",
                "comment": "Approved after department review.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, self.approved_status)
        self.assertEqual(self.requisition.status_history.count(), 2)

    def test_requester_cannot_apply_an_assigned_workflow_rule(self):
        rule = ProcurementWorkflowRule.objects.get(
            from_status=self.pending_status,
            to_status=self.approved_status,
            department=None,
        )
        self.requisition.requested_by = self.manager
        self.requisition.save()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse(
                "procurement:purchase_requisition_transition",
                args=(self.requisition.pk,),
            ),
            {"action": f"rule:{rule.pk}", "comment": "Self approval."},
        )
        self.assertEqual(response.status_code, 403)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, self.pending_status)

    def test_global_workflow_rule_can_be_assigned_to_a_role(self):
        review_status = ProcurementStatus.objects.create(
            name="Procurement Review",
            slug="procurement_review",
        )
        reviewer_role = Role.objects.create(
            name="Procurement Reviewer",
            slug="procurement_reviewer",
        )
        reviewer = User.objects.create_user(
            username="procurement-reviewer",
            password="test-password",
            role=reviewer_role,
        )
        rule = ProcurementWorkflowRule.objects.create(
            from_status=self.pending_status,
            to_status=review_status,
            action_label="Send to procurement review",
            approver_type=ProcurementWorkflowRule.ApproverType.ROLE,
            approver_role=reviewer_role,
        )
        self.requisition.requested_by = self.officer
        self.requisition.save()
        url = reverse(
            "procurement:purchase_requisition_transition",
            args=(self.requisition.pk,),
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            url,
            {"action": f"rule:{rule.pk}", "comment": "Not my assigned stage."},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(reviewer)
        response = self.client.post(
            url,
            {"action": f"rule:{rule.pk}", "comment": "Reviewed."},
        )
        self.assertEqual(response.status_code, 302)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, review_status)

    def test_inactive_department_rules_do_not_fall_back_to_global_approvers(self):
        department = ProcurementDepartment.objects.create(
            name="Finance",
            slug="finance",
        )
        review_status = ProcurementStatus.objects.create(
            name="Finance Review",
            slug="finance_review",
        )
        ProcurementWorkflowRule.objects.create(
            from_status=self.pending_status,
            to_status=review_status,
            department=department,
            action_label="Finance review",
            approver_type=ProcurementWorkflowRule.ApproverType.USER,
            approver_user=self.officer,
            is_active=False,
        )
        self.requisition.department = department
        self.requisition.requested_by = self.officer
        self.requisition.save()
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("procurement:purchase_requisition_list")
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-action="rule:')

    def test_workflow_routing_page_is_manageable(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("procurement:procurement_workflow_rule_list")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send for approval")
        self.assertContains(response, "Procurement managers")

    def test_requisition_moves_through_submission_approval_and_return_history(self):
        self.requisition.status = ProcurementStatus.objects.get(slug="draft")
        self.requisition.requested_by = self.officer
        self.requisition.save()
        transition_url = reverse(
            "procurement:purchase_requisition_transition",
            args=(self.requisition.pk,),
        )
        self.client.force_login(self.officer)
        self.assertEqual(
            self.client.post(transition_url, {"action": "approve"}).status_code,
            403,
        )

        self.client.force_login(self.superuser)
        for action, expected in (
            ("submit", "submitted"),
            ("send_for_approval", "pending_approval"),
            ("return", "returned"),
            ("submit", "submitted"),
            ("send_for_approval", "pending_approval"),
            ("approve", "approved"),
        ):
            response = self.client.post(
                transition_url,
                {"action": action, "comment": f"Moved to {expected}"},
            )
            self.assertEqual(response.status_code, 302)
            self.requisition.refresh_from_db()
            self.assertEqual(self.requisition.status.slug, expected)

        self.assertEqual(self.requisition.status_history.count(), 6)
        self.assertTrue(
            self.requisition.status_history.filter(
                from_status="pending_approval",
                to_status="approved",
                comment="Moved to approved",
                changed_by=self.superuser,
            ).exists()
        )
        list_response = self.client.get(
            reverse("procurement:purchase_requisition_list")
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Approved")

    def test_procurement_plan_actions_render_as_front_layer_dropdown(self):
        ProcurementPlan.objects.create(
            title="Visible actions plan",
            fiscal_year="2026",
            requested_by=self.superuser,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("procurement:procurement_plan_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-display="static"')
        self.assertContains(response, "document.body.appendChild(menu)")
        self.assertContains(response, "shown.bs.dropdown")
        self.assertContains(response, "hidden.bs.dropdown")

    def test_purchase_order_requires_approved_requisition_and_derives_total(self):
        self.client.force_login(self.superuser)
        url = reverse("procurement:purchase_order_add")
        response = self.client.post(url, {"quotation": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchaseOrder.objects.exists())

        self.requisition.status = self.approved_status
        self.requisition.save()
        quotation = self.create_quotation()
        response = self.client.post(url, {"quotation": str(quotation.pk)})
        self.assertEqual(response.status_code, 302)
        order = PurchaseOrder.objects.get()
        self.assertEqual(order.total_amount, Decimal("250.00"))
        self.assertFalse(order.approved)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.quotation, quotation)
        self.assertEqual(order.supplier, quotation.supplier)
        self.assertEqual(order.requisition, quotation.requisition)

    def test_legacy_purchase_order_edit_shows_items_and_keeps_unchanged_lines_in_total(self):
        self.requisition.status = self.approved_status
        self.requisition.save()
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            requisition=self.requisition,
            total_amount=Decimal("80.00"),
        )
        first_item = PurchaseOrderItem.objects.create(
            purchase_order=order,
            description="Examination couch",
            quantity=1,
            unit_price=Decimal("50.00"),
        )
        second_item = PurchaseOrderItem.objects.create(
            purchase_order=order,
            description="Stethoscope",
            quantity=2,
            unit_price=Decimal("15.00"),
        )
        self.client.force_login(self.superuser)
        edit_url = reverse("procurement:purchase_order_edit", args=(order.pk,))

        page = self.client.get(edit_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'name="items-0-description"')
        self.assertContains(page, "Add item")

        response = self.client.post(
            edit_url,
            {
                "quotation": "",
                "supplier": str(self.supplier.pk),
                "requisition": str(self.requisition.pk),
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "2",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": str(first_item.pk),
                "items-0-purchase_order": str(order.pk),
                "items-0-description": "Examination couch",
                "items-0-quantity": "1",
                "items-0-unit_price": "50.00",
                "items-0-DELETE": "",
                "items-1-id": str(second_item.pk),
                "items-1-purchase_order": str(order.pk),
                "items-1-description": "Stethoscope",
                "items-1-quantity": "2",
                "items-1-unit_price": "15.00",
                "items-1-DELETE": "",
                "items-2-description": "",
                "items-2-quantity": "1",
                "items-2-unit_price": "0",
                "items-2-DELETE": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
            (
                f"form errors: {response.context['form'].errors}; "
                f"formset errors: {response.context['formset'].errors}"
            ) if response.status_code == 200 else "",
        )
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("80.00"))
        self.assertEqual(order.items.count(), 2)

    def test_purchase_order_cannot_exceed_requisition_amount_or_use_blacklisted_supplier(self):
        self.requisition.status = self.approved_status
        self.requisition.save()
        self.client.force_login(self.superuser)
        url = reverse("procurement:purchase_order_add")
        quotation = self.create_quotation(
            total=Decimal("600.00"),
            description="Equipment",
            unit_price=Decimal("300.00"),
        )

        response = self.client.post(url, {"quotation": str(quotation.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchaseOrder.objects.exists())

        self.supplier.is_blacklisted = True
        self.supplier.save()
        response = self.client.post(url, {"quotation": str(quotation.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PurchaseOrder.objects.exists())

    def test_purchase_order_approval_is_post_only_and_manager_only(self):
        self.requisition.status = self.approved_status
        self.requisition.save()
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            requisition=self.requisition,
            quotation=self.create_quotation(
                total=Decimal("50.00"),
                description="Equipment",
                quantity=1,
                unit_price=Decimal("50.00"),
            ),
            total_amount=Decimal("50.00"),
        )
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            description="Equipment",
            quantity=1,
            unit_price=Decimal("50.00"),
        )
        approval_url = reverse(
            "procurement:purchase_order_approve",
            args=(order.pk,),
        )
        self.client.force_login(self.officer)

        self.assertEqual(self.client.get(approval_url).status_code, 405)
        self.assertEqual(self.client.post(approval_url).status_code, 403)
        order.refresh_from_db()
        self.assertFalse(order.approved)

        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(approval_url).status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.approved)
        self.assertIsNotNone(order.approved_at)

    def test_approved_order_cannot_be_changed_or_deleted(self):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            approved=True,
            total_amount=Decimal("50.00"),
        )
        self.client.force_login(self.superuser)

        edit_response = self.client.get(
            reverse("procurement:purchase_order_edit", args=(order.pk,))
        )
        delete_response = self.client.post(
            reverse("procurement:purchase_order_delete", args=(order.pk,))
        )

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(PurchaseOrder.objects.filter(pk=order.pk).exists())

    def test_purchase_order_api_derives_items_total_and_rejects_over_budget(self):
        self.requisition.status = self.approved_status
        self.requisition.save()
        quotation = self.create_quotation(
            total=Decimal("200.00"),
            description="Clinical equipment",
            unit_price=Decimal("100.00"),
        )
        request = type("Request", (), {"user": self.officer})()
        data = {
            "quotation": str(quotation.pk),
            "items": [
                {
                    "description": "Clinical equipment",
                    "quantity": 2,
                    "unit_price": "100.00",
                }
            ],
        }
        serializer = PurchaseOrderSerializer(
            data=data,
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.total_amount, Decimal("200.00"))

        over_budget_requisition = PurchaseRequisition.objects.create(
            title="Additional ward equipment",
            status=self.approved_status,
            total_amount=Decimal("500.00"),
        )
        over_budget_quotation = self.create_quotation(
            requisition=over_budget_requisition,
            total=Decimal("600.00"),
            description="Clinical equipment",
            unit_price=Decimal("300.00"),
        )
        data["quotation"] = str(over_budget_quotation.pk)
        data["items"][0]["unit_price"] = "300.00"
        serializer = PurchaseOrderSerializer(
            data=data,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("quotation", serializer.errors)

    def test_procurement_api_routes_are_reachable_and_permission_gated(self):
        client = APIClient()
        client.force_authenticate(self.officer)

        suppliers_response = client.get(reverse("procurement-supplier-list"))
        orders_for_officer_response = client.get(
            reverse("procurement-order-list")
        )

        self.assertEqual(suppliers_response.status_code, 200)
        self.assertEqual(orders_for_officer_response.status_code, 403)

        client.force_authenticate(self.manager)
        orders_for_manager_response = client.get(
            reverse("procurement-order-list")
        )

        self.assertEqual(orders_for_manager_response.status_code, 200)

    def test_requisition_exports_include_names_and_excel_downloads_are_real_xlsx_files(self):
        self.officer.first_name = "Taylor"
        self.officer.last_name = "Buyer"
        self.officer.save(update_fields=["first_name", "last_name"])
        self.requisition.requested_by = self.officer
        self.requisition.save(update_fields=["requested_by"])
        PurchaseOrder.objects.create(
            supplier=self.supplier,
            requisition=self.requisition,
            total_amount=Decimal("500.00"),
        )
        self.client.force_login(self.superuser)

        requisition_csv = self.client.get(
            reverse("procurement:export_purchase_requisition_csv")
        )
        self.assertEqual(requisition_csv.status_code, 200)
        csv_rows = list(csv.reader(StringIO(requisition_csv.content.decode())))
        self.assertEqual(csv_rows[1][2], "Taylor Buyer")

        requisition_xlsx = self.client.get(
            reverse("procurement:export_purchase_requisition_excel")
        )
        self.assertEqual(requisition_xlsx.status_code, 200)
        self.assertEqual(
            requisition_xlsx["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(".xlsx", requisition_xlsx["Content-Disposition"])
        workbook = load_workbook(BytesIO(requisition_xlsx.content), read_only=True)
        self.assertEqual(
            list(workbook.active.iter_rows(values_only=True))[1][2],
            "Taylor Buyer",
        )

        order_xlsx = self.client.get(
            reverse("procurement:export_purchase_order_excel")
        )
        self.assertEqual(order_xlsx.status_code, 200)
        self.assertTrue(order_xlsx.content.startswith(b"PK"))
        order_workbook = load_workbook(BytesIO(order_xlsx.content), read_only=True)
        order_rows = list(order_workbook.active.iter_rows(values_only=True))
        self.assertEqual(order_rows[1][0], self.supplier.name)
        self.assertEqual(order_rows[1][1], self.requisition.title)

    @patch(
        "django.core.files.storage.FileSystemStorage._save",
        return_value="procurement/quotations/supplier-quote.pdf",
    )
    def test_supplier_quotation_upload_review_selection_and_print(self, _save_file):
        self.requisition.status = self.approved_status
        self.requisition.save()
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("procurement:purchase_quotation_add"),
            {
                "supplier": str(self.supplier.pk),
                "requisition": str(self.requisition.pk),
                "reference": "SUP-QUOTE-2026-04",
                "date_received": "2026-10-18",
                "valid_until": "2026-12-01",
                "document": SimpleUploadedFile(
                    "supplier-quote.pdf",
                    b"%PDF-1.4",
                    content_type="application/pdf",
                ),
                "notes": "Sample supplier quotation for ward supplies.",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-description": "Examination couch",
                "items-0-quantity": "2",
                "items-0-unit_price": "125.50",
                "items-0-DELETE": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        quotation = PurchaseQuotation.objects.get()
        self.assertEqual(quotation.total_amount, Decimal("251.00"))
        self.assertEqual(quotation.items.count(), 1)
        self.assertEqual(
            quotation.document.name,
            "procurement/quotations/supplier-quote.pdf",
        )

        status_response = self.client.post(
            reverse(
                "procurement:purchase_quotation_change_status",
                args=(quotation.pk,),
            ),
            {"status": PurchaseQuotation.Status.ACCEPTED},
        )
        self.assertEqual(status_response.status_code, 302)
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, PurchaseQuotation.Status.RECEIVED)
        status_response = self.client.post(
            reverse(
                "procurement:purchase_quotation_change_status",
                args=(quotation.pk,),
            ),
            {"status": PurchaseQuotation.Status.UNDER_REVIEW},
        )
        self.assertEqual(status_response.status_code, 302)
        status_response = self.client.post(
            reverse(
                "procurement:purchase_quotation_change_status",
                args=(quotation.pk,),
            ),
            {"status": PurchaseQuotation.Status.ACCEPTED},
        )
        self.assertEqual(status_response.status_code, 302)
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, PurchaseQuotation.Status.ACCEPTED)

        detail_response = self.client.get(
            reverse(
                "procurement:purchase_quotation_detail",
                args=(quotation.pk,),
            )
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Open attached quotation")
        self.assertContains(detail_response, "251.00")

    def test_only_one_supplier_quotation_can_be_selected_per_requisition(self):
        self.requisition.status = self.approved_status
        self.requisition.save()
        first = self.create_quotation(
            total=Decimal("100.00"),
            status=PurchaseQuotation.Status.UNDER_REVIEW,
            quantity=1,
            unit_price=Decimal("100.00"),
        )
        second = self.create_quotation(
            total=Decimal("120.00"),
            status=PurchaseQuotation.Status.UNDER_REVIEW,
            description="Ward monitor",
            quantity=1,
            unit_price=Decimal("120.00"),
        )
        self.client.force_login(self.superuser)
        url = reverse(
            "procurement:purchase_quotation_change_status",
            args=(first.pk,),
        )
        self.assertEqual(
            self.client.post(url, {"status": PurchaseQuotation.Status.ACCEPTED}).status_code,
            302,
        )
        url = reverse(
            "procurement:purchase_quotation_change_status",
            args=(second.pk,),
        )
        self.assertEqual(
            self.client.post(url, {"status": PurchaseQuotation.Status.ACCEPTED}).status_code,
            302,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, PurchaseQuotation.Status.ACCEPTED)
        self.assertEqual(second.status, PurchaseQuotation.Status.UNDER_REVIEW)
        self.assertEqual(
            PurchaseQuotation.objects.filter(
                requisition=self.requisition,
                status=PurchaseQuotation.Status.ACCEPTED,
            ).count(),
            1,
        )

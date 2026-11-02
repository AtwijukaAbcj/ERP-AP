from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Permission, Student, User, UserPermission
from core.models import Semester, Session
from course.models import Program

from .models import (
    BankReconciliation,
    Budget,
    CashBookEntry,
    ExpenseCategory,
    FeeCategory,
    FinanceModulePermission,
    GeneralLedgerEntry,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    LedgerAccount,
    OnlineInvoicePayment,
    PaymentVoucher,
    Payroll,
    Staff,
    StaffDepartment,
)
from .serializers import InvoiceSerializer, StaffSerializer
from .views import student_invoice_detail


@override_settings(LANGUAGE_CODE="en", ONLINE_PAYMENT_CURRENCY="USD")
class StudentBillingTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.student_user = User.objects.create_user(
            username="billing-student",
            password="test-password",
            is_student=True,
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        self.other_user = User.objects.create_user(
            username="other-student",
            password="test-password",
            is_student=True,
        )
        self.other_student = Student.objects.create(
            student=self.other_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        self.category = FeeCategory.objects.create(
            name="Tuition",
            amount=Decimal("1000.00"),
            semester=self.semester,
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            semester=self.semester,
            due_date=date(2026, 11, 30),
            total_amount=Decimal("1000.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            category=self.category,
            amount=Decimal("1000.00"),
        )
        self.finance_user = User.objects.create_user(
            username="finance-manager",
            password="test-password",
            is_finance_manager=True,
        )

    def test_student_can_only_see_their_own_invoices(self):
        Invoice.objects.create(
            student=self.other_student,
            semester=self.semester,
            due_date=date(2026, 11, 30),
            total_amount=Decimal("1000.00"),
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("finance:student_invoices"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"INV{self.invoice.pk:05d}")
        self.assertNotContains(response, f"INV{self.invoice.pk + 1:05d}")
        request = RequestFactory().get(
            reverse("finance:view_student_invoice", args=(self.invoice.pk + 1,))
        )
        request.user = self.student_user
        with self.assertRaises(Http404):
            student_invoice_detail(request, self.invoice.pk + 1)

    def test_student_cannot_view_staff_invoice_listing(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("finance:invoice_list"))

        self.assertEqual(response.status_code, 403)

    def test_invoice_list_keeps_action_buttons_inside_scrollable_table(self):
        admin = User.objects.create_superuser(
            username="invoice-table-admin",
            email="invoice-table-admin@example.test",
            password="test-password",
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("finance:invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invoice-table-responsive")
        self.assertContains(response, "min-width: 1280px")
        self.assertContains(response, "min-width: 148px")
        self.assertContains(response, 'id="invoiceActions')
        self.assertContains(response, "fa-ellipsis-v")
        self.assertContains(response, "Add Category")
        self.assertContains(response, 'menu-dropdown orange open')
        self.assertContains(
            response,
            'href="/en/finance/invoices/" class="active" aria-current="page"',
        )
        self.assertContains(response, "shown.bs.dropdown")
        self.assertContains(response, "hidden.bs.dropdown")
        self.assertContains(response, reverse("finance:view_invoice", args=(self.invoice.pk,)))
        self.assertContains(response, reverse("finance:edit_invoice", args=(self.invoice.pk,)))
        self.assertContains(response, reverse("finance:download_invoice_pdf", args=(self.invoice.pk,)))

    def test_invoice_list_only_shows_add_category_with_fee_category_access(self):
        finance_user = User.objects.create_user(
            username="invoice-category-access",
            email="invoice-category-access@example.test",
            password="Test-password-123!",
            is_finance=True,
        )
        FinanceModulePermission.objects.create(
            staff=finance_user,
            module_name="manage_invoices",
        )
        self.client.force_login(finance_user)

        response = self.client.get(reverse("finance:invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add Category")

        FinanceModulePermission.objects.create(
            staff=finance_user,
            module_name="fee_category_add",
        )
        response = self.client.get(reverse("finance:invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("finance:fee_category_add"))
        self.assertContains(response, "Add Category")

    def test_invoice_and_payment_receipt_pdfs_are_valid_and_private(self):
        payment = InvoicePayment.objects.create(
            invoice=self.invoice,
            amount=Decimal("125.00"),
            payment_date=date(2026, 10, 18),
            method=InvoicePayment.Method.BANK,
            reference="DEMO-RECEIPT-001",
        )
        self.client.force_login(self.student_user)

        invoice_response = self.client.get(
            reverse("finance:download_invoice_pdf", args=(self.invoice.pk,))
        )
        self.assertEqual(invoice_response.status_code, 200)
        self.assertTrue(invoice_response.content.startswith(b"%PDF"))

        receipt_url = reverse(
            "finance:download_payment_receipt_pdf",
            args=(payment.pk,),
        )
        receipt_response = self.client.get(receipt_url)
        self.assertEqual(receipt_response.status_code, 200)
        self.assertTrue(receipt_response.content.startswith(b"%PDF"))
        self.assertIn(
            'receipt_000001.pdf',
            receipt_response["Content-Disposition"],
        )

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(receipt_url).status_code, 403)

    def test_invoice_detail_displays_payment_form_and_history(self):
        self.client.force_login(self.finance_user)

        response = self.client.get(
            reverse("finance:view_invoice", args=(self.invoice.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment History")
        self.assertContains(response, "Record Payment")

    def test_invoice_api_keeps_payment_totals_read_only_and_recalculates_status(self):
        self.invoice.paid_amount = Decimal("1000.00")
        self.invoice.status = "paid"
        self.invoice.save()

        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "total_amount": "1200.00",
                "paid_amount": "0.00",
                "status": "paid",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_invoice = serializer.save()
        self.assertEqual(updated_invoice.paid_amount, Decimal("1000.00"))
        self.assertEqual(updated_invoice.status, "partial")

    def test_semester_invoice_generation_applies_general_and_student_fees_once(self):
        FeeCategory.objects.create(
            name="Individual clinical kit",
            amount=Decimal("75.00"),
            semester=self.semester,
            student=self.student,
        )
        FeeCategory.objects.create(
            name="Other student fee",
            amount=Decimal("40.00"),
            semester=self.semester,
            student=self.other_student,
        )
        self.client.force_login(self.finance_user)

        response = self.client.post(
            reverse("finance:generate_semester_invoices"),
            {"due_date": "2026-11-30"},
        )

        self.assertRedirects(response, reverse("finance:invoice_list"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.items.count(), 1)
        generated = Invoice.objects.get(student=self.other_student)
        self.assertEqual(generated.total_amount, Decimal("1040.00"))
        self.assertEqual(generated.items.count(), 2)

        self.client.post(
            reverse("finance:generate_semester_invoices"),
            {"due_date": "2026-11-30"},
        )
        self.assertEqual(
            Invoice.objects.filter(semester=self.semester).count(),
            2,
        )

    def test_manual_invoice_total_is_derived_from_items(self):
        self.client.force_login(self.finance_user)

        response = self.client.post(
            reverse("finance:create_invoice"),
            {
                "student": self.other_student.pk,
                "semester": self.semester.pk,
                "due_date": "2026-11-30",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-category": self.category.pk,
                "items-0-amount": "250.00",
            },
        )

        self.assertRedirects(response, reverse("finance:invoice_list"))
        created = Invoice.objects.get(student=self.other_student)
        self.assertEqual(created.total_amount, Decimal("250.00"))
        self.assertEqual(created.items.count(), 1)

    def test_recording_payments_tracks_partial_and_full_settlement(self):
        self.client.force_login(self.finance_user)
        payment_url = reverse(
            "finance:record_invoice_payment",
            args=(self.invoice.pk,),
        )

        response = self.client.post(
            payment_url,
            {
                "amount": "400.00",
                "payment_date": "2026-10-18",
                "method": InvoicePayment.Method.BANK,
                "reference": "BANK-001",
            },
        )

        self.assertRedirects(
            response,
            reverse("finance:view_invoice", args=(self.invoice.pk,)),
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("400.00"))
        self.assertEqual(self.invoice.status, "partial")
        self.assertEqual(self.invoice.payments.count(), 1)

        self.client.post(
            payment_url,
            {
                "amount": "600.00",
                "payment_date": "2026-10-18",
                "method": InvoicePayment.Method.CASH,
            },
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.00"))
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(self.invoice.payments.count(), 2)

    def test_payment_cannot_exceed_balance_or_be_recorded_by_student(self):
        self.client.force_login(self.finance_user)
        response = self.client.post(
            reverse("finance:record_invoice_payment", args=(self.invoice.pk,)),
            {
                "amount": "1000.01",
                "payment_date": "2026-10-18",
                "method": InvoicePayment.Method.CASH,
            },
        )
        self.invoice.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.invoice.paid_amount, Decimal("0.00"))
        self.assertFalse(InvoicePayment.objects.exists())

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("finance:record_invoice_payment", args=(self.invoice.pk,)),
            {
                "amount": "1.00",
                "payment_date": "2026-10-18",
                "method": InvoicePayment.Method.CASH,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InvoicePayment.objects.exists())

    @patch("finance.views.create_stripe_checkout")
    def test_stripe_checkout_records_only_a_verified_payment(self, create_checkout):
        create_checkout.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        self.client.force_login(self.student_user)
        start_url = reverse(
            "finance:start_online_invoice_payment",
            args=(self.invoice.pk, OnlineInvoicePayment.Provider.STRIPE),
        )

        response = self.client.post(start_url)

        self.assertRedirects(
            response,
            "https://checkout.stripe.test/session",
            fetch_redirect_response=False,
        )
        attempt = OnlineInvoicePayment.objects.get(invoice=self.invoice)
        self.assertEqual(attempt.status, OnlineInvoicePayment.Status.PENDING)
        self.assertEqual(attempt.provider_session_id, "cs_test_123")
        self.assertFalse(InvoicePayment.objects.exists())

        confirmed_session = SimpleNamespace(
            id="cs_test_123",
            status="complete",
            payment_status="paid",
            client_reference_id=str(attempt.pk),
            metadata={
                "attempt_id": str(attempt.pk),
                "invoice_id": str(self.invoice.pk),
            },
            amount_total=100000,
            currency="usd",
            payment_intent="pi_test_123",
        )
        callback_url = reverse("finance:stripe_payment_success")
        with patch(
            "finance.views.retrieve_stripe_checkout",
            return_value=confirmed_session,
        ):
            response = self.client.get(
                callback_url,
                {
                    "attempt": attempt.pk,
                    "session_id": "cs_test_123",
                },
            )
            self.assertEqual(response.status_code, 302)
            response = self.client.get(
                callback_url,
                {
                    "attempt": attempt.pk,
                    "session_id": "cs_test_123",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.00"))
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(attempt.status, OnlineInvoicePayment.Status.SUCCEEDED)
        self.assertEqual(self.invoice.payments.count(), 1)
        self.assertEqual(
            self.invoice.payments.get().method,
            InvoicePayment.Method.CARD,
        )

    @patch("finance.views.create_paypal_order")
    @patch("finance.views.capture_paypal_order")
    def test_paypal_capture_is_verified_before_invoice_payment(
        self,
        capture_order,
        create_order,
    ):
        create_order.return_value = (
            "ORDER-123",
            "https://www.paypal.test/checkout",
        )
        self.client.force_login(self.student_user)
        start_url = reverse(
            "finance:start_online_invoice_payment",
            args=(self.invoice.pk, OnlineInvoicePayment.Provider.PAYPAL),
        )

        response = self.client.post(start_url)

        self.assertRedirects(
            response,
            "https://www.paypal.test/checkout",
            fetch_redirect_response=False,
        )
        attempt = OnlineInvoicePayment.objects.get(invoice=self.invoice)
        capture_order.return_value = {
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "custom_id": str(attempt.pk),
                    "payments": {
                        "captures": [
                            {
                                "id": "CAPTURE-123",
                                "status": "COMPLETED",
                                "amount": {
                                    "currency_code": "USD",
                                    "value": "1000.00",
                                },
                            }
                        ]
                    }
                }
            ],
        }

        response = self.client.get(
            reverse("finance:paypal_payment_return"),
            {"attempt": attempt.pk, "token": "ORDER-123"},
        )

        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("1000.00"))
        self.assertEqual(
            self.invoice.payments.get().method,
            InvoicePayment.Method.PAYPAL,
        )
        self.assertEqual(
            self.invoice.payments.get().reference,
            "paypal:CAPTURE-123",
        )

    @patch("finance.views.retrieve_stripe_checkout")
    @patch("finance.views.create_stripe_checkout")
    def test_unpaid_stripe_session_cannot_mark_invoice_as_paid(
        self,
        create_checkout,
        retrieve_checkout,
    ):
        create_checkout.return_value = SimpleNamespace(
            id="cs_unpaid_123",
            url="https://checkout.stripe.test/unpaid",
        )
        self.client.force_login(self.student_user)
        self.client.post(
            reverse(
                "finance:start_online_invoice_payment",
                args=(self.invoice.pk, OnlineInvoicePayment.Provider.STRIPE),
            )
        )
        attempt = OnlineInvoicePayment.objects.get(invoice=self.invoice)
        retrieve_checkout.return_value = SimpleNamespace(
            id="cs_unpaid_123",
            status="open",
            payment_status="unpaid",
            client_reference_id=str(attempt.pk),
            metadata={
                "attempt_id": str(attempt.pk),
                "invoice_id": str(self.invoice.pk),
            },
            amount_total=100000,
            currency="usd",
            payment_intent=None,
        )

        response = self.client.get(
            reverse("finance:stripe_payment_success"),
            {
                "attempt": attempt.pk,
                "session_id": "cs_unpaid_123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("0.00"))
        self.assertEqual(attempt.status, OnlineInvoicePayment.Status.PENDING)
        self.assertFalse(InvoicePayment.objects.exists())

    def test_finance_report_is_permission_gated_and_shows_invoice_totals(self):
        self.client.force_login(self.finance_user)

        response = self.client.get(reverse("finance:finance_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice_total"], Decimal("1000.00"))
        self.assertEqual(
            response.context["invoice_outstanding"],
            Decimal("1000.00"),
        )

        self.client.force_login(self.student_user)
        self.assertEqual(
            self.client.get(reverse("finance:finance_reports")).status_code,
            403,
        )


@override_settings(LANGUAGE_CODE="en")
class AccountingListRenderingTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(
            username="accounting-list-admin",
            email="accounting-list-admin@example.test",
            password="Test-password-123!",
        )
        self.client.force_login(admin)
        session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        Semester.objects.create(
            semester="First",
            session=session,
            is_current_semester=True,
        )

    def test_static_finance_pages_render_for_superuser(self):
        from .urls import urlpatterns

        student_only_pages = {
            "student_invoices",
            "stripe_payment_success",
            "paypal_payment_return",
        }
        page_names = [
            pattern.name
            for pattern in urlpatterns
            if pattern.name
            and "<" not in str(pattern.pattern)
            and pattern.name not in student_only_pages
        ]

        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"finance:{page_name}"))
                self.assertEqual(response.status_code, 200)

    def test_accounting_entry_forms_use_the_shared_styled_form_layout(self):
        page_names = (
            "cash_book_add",
            "budget_add",
            "bank_reconciliation_add",
            "general_ledger_add",
            "ledger_account_add",
            "payment_voucher_add",
        )
        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"finance:{page_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "finance-form-page")
                self.assertContains(response, 'class="form-control')
                self.assertNotContains(response, "form.as_p")

    def test_accounting_pages_require_the_matching_finance_module_grant(self):
        finance_user = User.objects.create_user(
            username="accounting-module-user",
            email="accounting-module-user@example.test",
            password="Test-password-123!",
            is_finance=True,
        )
        self.client.force_login(finance_user)
        module_pages = {
            "expense_category_list": (
                "expense_category_list",
                "expense_category_add",
            ),
            "expense_list": ("expense_list", "expense_add"),
            "petty_cash_list": ("petty_cash_list", "petty_cash_add"),
            "accounts_payable_list": (
                "accounts_payable_list",
                "accounts_payable_add",
            ),
            "accounts_receivable_list": (
                "accounts_receivable_list",
                "accounts_receivable_add",
            ),
            "budget_list": ("budget_list", "budget_add"),
            "cash_book_list": ("cash_book_list", "cash_book_add"),
            "bank_reconciliation_list": (
                "bank_reconciliation_list",
                "bank_reconciliation_add",
            ),
            "ledger_account_list": ("ledger_account_list", "ledger_account_add"),
            "general_ledger_list": ("general_ledger_list", "general_ledger_add"),
            "payment_voucher_list": (
                "payment_voucher_list",
                "payment_voucher_add",
            ),
        }

        for module_name, page_names in module_pages.items():
            with self.subTest(module=module_name):
                for page_name in page_names:
                    url = reverse(f"finance:{page_name}")
                    self.assertEqual(self.client.get(url).status_code, 403)

                FinanceModulePermission.objects.create(
                    staff=finance_user,
                    module_name=module_name,
                )
                for page_name in page_names:
                    url = reverse(f"finance:{page_name}")
                    self.assertEqual(self.client.get(url).status_code, 200)

                FinanceModulePermission.objects.filter(
                    staff=finance_user,
                    module_name=module_name,
                ).delete()

    def test_accounting_lists_render_when_optional_users_are_missing(self):
        Budget.objects.create(
            title="Operating Budget",
            department="Administration",
            fiscal_year="2026/2027",
        )
        CashBookEntry.objects.create(date=date(2026, 11, 1))
        BankReconciliation.objects.create(
            bank_name="Example Bank",
            statement_date=date(2026, 11, 1),
            book_balance=Decimal("100.00"),
            bank_balance=Decimal("100.00"),
        )
        account = LedgerAccount.objects.create(code="1000", name="Cash")
        GeneralLedgerEntry.objects.create(
            account=account,
            date=date(2026, 11, 1),
            description="Opening balance",
        )
        PaymentVoucher.objects.create(
            voucher_number="PV-2026-001",
            title="Office supplies",
            vendor_name="Example Vendor",
            amount=Decimal("50.00"),
        )

        pages = (
            "finance:budget_list",
            "finance:cash_book_list",
            "finance:bank_reconciliation_list",
            "finance:general_ledger_list",
            "finance:payment_voucher_list",
        )
        for page in pages:
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "—")


@override_settings(LANGUAGE_CODE="en")
class FeeCategoryManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="fee-category-admin",
            email="fee-category-admin@example.test",
            password="Fee-Category-Test-Password-123!",
        )
        self.session = Session.objects.create(
            session="2026/2027",
            is_current_session=True,
        )
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.category = FeeCategory.objects.create(
            name="Tuition",
            description="Original description",
            amount=Decimal("1000.00"),
            semester=self.semester,
        )
        self.client.force_login(self.admin)

    def test_fee_category_list_shows_edit_action(self):
        response = self.client.get(reverse("finance:fee_category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.category.name)
        self.assertContains(response, "fa-ellipsis-v")
        self.assertContains(
            response,
            reverse("finance:fee_category_edit", args=(self.category.pk,)),
        )
        self.assertContains(
            response,
            reverse("finance:fee_category_delete", args=(self.category.pk,)),
        )
        self.assertContains(response, reverse("finance:fee_category_add"))
        self.assertContains(response, "Delete")

    def test_fee_category_can_be_edited(self):
        edit_url = reverse("finance:fee_category_edit", args=(self.category.pk,))

        response = self.client.get(edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Fee Category")
        self.assertContains(response, 'value="Tuition"')

        response = self.client.post(
            edit_url,
            {
                "name": "Updated Tuition",
                "description": "Updated description",
                "amount": "1250.00",
                "semester": str(self.semester.pk),
                "student": "",
            },
        )

        self.assertRedirects(response, reverse("finance:fee_category_list"))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Updated Tuition")
        self.assertEqual(self.category.description, "Updated description")
        self.assertEqual(self.category.amount, Decimal("1250.00"))

    def test_unused_fee_category_delete_is_post_only(self):
        delete_url = reverse(
            "finance:fee_category_delete",
            args=(self.category.pk,),
        )

        response = self.client.get(delete_url)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(FeeCategory.objects.filter(pk=self.category.pk).exists())

        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse("finance:fee_category_list"))
        self.assertFalse(FeeCategory.objects.filter(pk=self.category.pk).exists())

    def test_fee_category_used_by_an_invoice_cannot_be_deleted(self):
        student_user = User.objects.create_user(
            username="fee-category-student",
            password="test-pass",
            is_student=True,
        )
        student = Student.objects.create(
            student=student_user,
            program=Program.objects.create(title="Fee Category Program"),
            level="Bachelor",
            year=1,
        )
        invoice = Invoice.objects.create(
            student=student,
            semester=self.semester,
            due_date=date(2026, 11, 30),
            total_amount=Decimal("1000.00"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            category=self.category,
            amount=Decimal("1000.00"),
        )

        response = self.client.get(reverse("finance:fee_category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse("finance:fee_category_delete", args=(self.category.pk,)),
        )
        self.assertContains(response, "Used by an invoice")

        response = self.client.post(
            reverse("finance:fee_category_delete", args=(self.category.pk,))
        )

        self.assertRedirects(response, reverse("finance:fee_category_list"))
        self.assertTrue(FeeCategory.objects.filter(pk=self.category.pk).exists())

    def test_fee_category_actions_are_hidden_and_protected_without_category_access(self):
        finance_user = User.objects.create_user(
            username="invoice-only-finance-user",
            password="test-pass",
            is_finance=True,
        )
        FinanceModulePermission.objects.create(
            staff=finance_user,
            module_name="manage_invoices",
        )
        self.client.force_login(finance_user)

        response = self.client.get(reverse("finance:fee_category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse("finance:fee_category_edit", args=(self.category.pk,)),
        )
        self.assertNotContains(response, reverse("finance:fee_category_add"))
        self.assertEqual(
            self.client.get(reverse("finance:fee_category_add")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("finance:fee_category_edit", args=(self.category.pk,))
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("finance:fee_category_delete", args=(self.category.pk,))
            ).status_code,
            403,
        )

        FinanceModulePermission.objects.create(
            staff=finance_user,
            module_name="fee_category_add",
        )
        response = self.client.get(reverse("finance:fee_category_list"))
        self.assertContains(
            response,
            reverse("finance:fee_category_edit", args=(self.category.pk,)),
        )

    def test_action_permissions_can_be_granted_and_denied_per_user(self):
        finance_user = User.objects.create_user(
            username="fee-action-user",
            password="Fee-Action-Test-Password-123!",
            is_finance=True,
        )
        FinanceModulePermission.objects.create(
            staff=finance_user,
            module_name="manage_invoices",
        )
        edit_permission = Permission.objects.get(
            code="finance.fee_category.edit",
        )
        UserPermission.objects.create(
            user=finance_user,
            permission=edit_permission,
            effect=UserPermission.GRANT,
        )
        self.client.force_login(finance_user)

        response = self.client.get(reverse("finance:fee_category_list"))

        self.assertContains(
            response,
            reverse("finance:fee_category_edit", args=(self.category.pk,)),
        )
        self.assertNotContains(
            response,
            reverse("finance:fee_category_delete", args=(self.category.pk,)),
        )
        self.assertEqual(
            self.client.get(
                reverse("finance:fee_category_edit", args=(self.category.pk,))
            ).status_code,
            200,
        )

        UserPermission.objects.update_or_create(
            user=finance_user,
            permission=edit_permission,
            defaults={"effect": UserPermission.DENY},
        )
        response = self.client.get(reverse("finance:fee_category_list"))
        self.assertNotContains(
            response,
            reverse("finance:fee_category_edit", args=(self.category.pk,)),
        )
        self.assertEqual(
            self.client.get(
                reverse("finance:fee_category_edit", args=(self.category.pk,))
            ).status_code,
            403,
        )


@override_settings(LANGUAGE_CODE="en")
class ExpenseCategoryManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="expense-category-admin",
            email="expense-category-admin@example.test",
            password="test-password",
        )
        self.category = ExpenseCategory.objects.create(name="Office Supplies")

    def test_category_list_links_to_edit_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("finance:expense_category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.category.name)
        self.assertContains(
            response,
            reverse("finance:expense_category_edit", args=(self.category.pk,)),
        )
        self.assertContains(response, 'class="table-action-cell"')
        self.assertContains(response, 'class="table-actions"')
        self.assertContains(response, 'class="btn btn-sm btn-outline-primary table-action-button"')
        self.assertContains(response, "fa-pen-to-square")
        self.assertNotContains(response, "category.description")

    def test_category_can_be_edited(self):
        self.client.force_login(self.admin)
        edit_url = reverse(
            "finance:expense_category_edit",
            args=(self.category.pk,),
        )

        response = self.client.get(edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Expense Category")
        self.assertContains(response, 'value="Office Supplies"')

        response = self.client.post(edit_url, {"name": "Office Equipment"})

        self.assertRedirects(
            response,
            reverse("finance:expense_category_list"),
        )
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Office Equipment")

    def test_category_edit_rejects_duplicate_name(self):
        ExpenseCategory.objects.create(name="Travel")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "finance:expense_category_edit",
                args=(self.category.pk,),
            ),
            {"name": "Travel"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Office Supplies")


@override_settings(LANGUAGE_CODE="en")
class StaffDepartmentManagementTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="staff-manager",
            password="test-password",
            is_staff=True,
            is_finance_manager=True,
        )
        self.employee_user = User.objects.create_user(
            username="department-employee",
            password="test-password",
            first_name="Ward",
            last_name="Nurse",
            is_staff=True,
        )
        self.department = StaffDepartment.objects.create(
            name="Clinical Training",
            code="CLIN",
            head=self.manager,
        )
        self.staff = Staff.objects.create(
            user=self.employee_user,
            department=self.department,
            employee_id="EMP-001",
            job_title="Nurse Educator",
        )

    def test_department_list_and_add_are_connected_to_staff_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("finance:staff_department_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clinical Training")
        self.assertContains(response, reverse("finance:staff_department_add"))
        self.assertEqual(
            self.client.get(
                reverse("finance:staff_department_add")
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "finance:staff_department_edit",
                    args=(self.department.pk,),
                )
            ).status_code,
            200,
        )

        response = self.client.post(
            reverse("finance:staff_department_add"),
            {
                "name": "Student Affairs",
                "code": "STUAFF",
                "faculty": "",
                "head": str(self.manager.pk),
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("finance:staff_department_list"),
        )
        self.assertTrue(
            StaffDepartment.objects.filter(code="STUAFF").exists()
        )

    def test_staff_record_can_be_assigned_to_a_department(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("finance:staff_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clinical Training")
        self.assertContains(
            response,
            reverse("finance:staff_department_list"),
        )

        response = self.client.post(
            reverse("finance:staff_add"),
            {
                "user": str(self.manager.pk),
                "category": "",
                "department": str(self.department.pk),
                "employee_id": "EMP-002",
                "job_title": "Registrar",
                "date_hired": "2025-01-15",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("finance:staff_list"))
        self.assertEqual(
            Staff.objects.get(employee_id="EMP-002").department,
            self.department,
        )

    def test_deactivating_staff_preserves_payroll_history(self):
        payroll = Payroll.objects.create(
            staff=self.staff,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            gross_amount=Decimal("1000.00"),
            net_amount=Decimal("1000.00"),
        )
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("finance:staff_edit", args=(self.staff.pk,)),
            {
                "user": str(self.employee_user.pk),
                "category": "",
                "department": str(self.department.pk),
                "employee_id": "EMP-001",
                "job_title": "Nurse Educator",
                "date_hired": "",
            },
        )

        self.assertRedirects(response, reverse("finance:staff_list"))
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.assertTrue(Payroll.objects.filter(pk=payroll.pk).exists())

    def test_inactive_department_cannot_be_assigned_through_api(self):
        self.department.is_active = False
        self.department.save(update_fields=["is_active"])

        serializer = StaffSerializer(
            self.staff,
            data={"department": self.department.pk},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("department", serializer.errors)

    def test_department_api_is_available_only_to_finance_managers(self):
        endpoint = reverse("staff-department-list")
        api_client = APIClient()
        api_client.force_authenticate(user=self.manager)
        response = api_client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        departments = payload.get("results", payload)
        self.assertEqual(departments[0]["code"], "CLIN")

        ordinary_user = User.objects.create_user(
            username="unprivileged-department-viewer",
            password="test-password",
        )
        api_client.force_authenticate(user=ordinary_user)
        self.assertEqual(api_client.get(endpoint).status_code, 403)

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.db import IntegrityError
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.templatetags.static import static

from .models import (
    AccountPayable,
    AccountReceivable,
    BankReconciliation,
    Budget,
    CashBookEntry,
    Expense,
    ExpenseCategory,
    FeeCategory,
    FinanceModulePermission,
    GeneralLedgerEntry,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    LedgerAccount,
    Payroll,
    PaymentVoucher,
    PettyCashEntry,
    Staff,
    StaffCategory,
    StaffDepartment,
    MODULE_CHOICES,
    OnlineInvoicePayment,
)
from .forms import (
    AccountPayableForm,
    AccountReceivableForm,
    BankReconciliationForm,
    BudgetForm,
    CashBookEntryForm,
    ExpenseCategoryForm,
    ExpenseForm,
    FeeCategoryForm,
    GeneralLedgerEntryForm,
    InvoiceForm,
    InvoiceItemFormSet,
    InvoicePaymentForm,
    SemesterInvoiceGenerationForm,
    LedgerAccountForm,
    PayrollForm,
    PaymentVoucherForm,
    PettyCashEntryForm,
    StaffCategoryForm,
    StaffDepartmentForm,
    StaffForm,
)
from accounts.models import User
from accounts.decorators import admin_required
from core.models import Semester, SiteSettings
from core.pdf_utils import pdf_link_callback
import csv
import io
from decimal import Decimal
from django.db.models import Exists, OuterRef, Sum
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.utils import timezone
from .permissions import (
    finance_action_permission_required,
    finance_permission_required,
    has_finance_action_permission,
    has_finance_permission,
)
from .services import create_semester_invoices, record_invoice_payment
from .services import create_online_invoice_payment, finalize_online_invoice_payment
from .payment_providers import (
    PaymentProviderError,
    capture_paypal_order,
    create_paypal_order,
    create_stripe_checkout,
    retrieve_stripe_checkout,
)


@login_required
def download_invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if not (
        request.user.is_student
        and invoice.student.student_id == request.user.pk
    ) and not has_finance_permission(
        request.user,
        "manage_invoices",
        "view_student_invoices",
    ):
        return HttpResponseForbidden("You are not authorized to view this invoice.")
    items = InvoiceItem.objects.filter(invoice=invoice)
    balance = invoice.total_amount - invoice.paid_amount
    site_settings = SiteSettings.get_settings()
    if site_settings.logo:
        logo_url = request.build_absolute_uri(site_settings.logo.url)
    else:
        logo_url = request.build_absolute_uri(static('img/logo.png'))

    template = get_template("finance/invoice_pdf_template.html")
    html = template.render({
        "invoice": invoice,
        "items": items,
        "balance": balance,
        "logo_url": logo_url,
        "site_settings": site_settings,
        "school_name": site_settings.school_name or "Unity College",
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.id}.pdf"'

    pisa_status = pisa.CreatePDF(
        io.BytesIO(html.encode("UTF-8")),
        dest=response,
        link_callback=pdf_link_callback,
    )
    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)

    return response


@login_required
def download_payment_receipt_pdf(request, payment_id):
    payment = get_object_or_404(
        InvoicePayment.objects.select_related(
            "invoice__student__student",
            "invoice__student__program",
            "invoice__semester__session",
            "recorded_by",
        ),
        pk=payment_id,
    )
    is_owner = (
        request.user.is_student
        and payment.invoice.student.student_id == request.user.pk
    )
    can_view_finance = has_finance_permission(
        request.user,
        "manage_invoices",
        "view_student_invoices",
    )
    if not (is_owner or can_view_finance):
        return HttpResponseForbidden("You are not authorized to view this receipt.")

    site_settings = SiteSettings.get_settings()
    logo_url = (
        request.build_absolute_uri(site_settings.logo.url)
        if site_settings.logo
        else request.build_absolute_uri(static("img/logo.png"))
    )
    html = get_template("finance/payment_receipt_pdf.html").render(
        {
            "payment": payment,
            "invoice": payment.invoice,
            "receipt_number": f"RCT{payment.pk:06d}",
            "invoice_number": f"INV{payment.invoice.pk:05d}",
            "site_settings": site_settings,
            "logo_url": logo_url,
        }
    )
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="receipt_{payment.pk:06d}.pdf"'
    )
    pdf_status = pisa.CreatePDF(
        io.BytesIO(html.encode("UTF-8")),
        dest=response,
        link_callback=pdf_link_callback,
    )
    if pdf_status.err:
        return HttpResponse("Error generating payment receipt.", status=500)
    return response


@login_required
def finance_dashboard(request):
    return render(request, 'finance/home.html')


@login_required
@finance_permission_required("manage_invoices")
def invoice_list(request):
    invoices = Invoice.objects.select_related(
        "student__student",
        "semester",
    ).prefetch_related("items__category").all()
    return render(
        request,
        'finance/manage_invoices.html',
        {
            'invoices': invoices,
            'can_add_fee_categories': has_finance_action_permission(
                request.user,
                "finance.fee_category.add",
                "manage_fee_categories",
                "fee_category_add",
            ),
        },
    )


@login_required
@finance_permission_required("create_invoice", "manage_invoices")
def create_invoice(request):
    invoice = Invoice()
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
        formset = InvoiceItemFormSet(request.POST, instance=invoice)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                items = formset.save(commit=False)
                invoice.total_amount = sum(
                    (item.amount for item in items),
                    start=Decimal("0.00"),
                )
                invoice.save()
                for item in items:
                    item.invoice = invoice
                    item.save()
                formset.save_m2m()
                invoice.update_status()
            return redirect('finance:invoice_list')
    else:
        form = InvoiceForm()
        formset = InvoiceItemFormSet(instance=invoice)

    return render(request, 'finance/create_invoice.html', {
        'form': form,
        'formset': formset,
    })

@login_required
@finance_permission_required("manage_invoices")
def invoice_edit(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, instance=invoice)
        if invoice_form.is_valid():
            invoice = invoice_form.save(commit=False)
        formset = InvoiceItemFormSet(request.POST, instance=invoice)

        if invoice_form.is_valid() and formset.is_valid():
            items = formset.save(commit=False)
            new_total = sum(
                (item.amount for item in items),
                start=Decimal("0.00"),
            )
            if new_total < invoice.paid_amount:
                formset.add_error(
                    None,
                    "Invoice items cannot reduce the total below the amount already paid.",
                )
            else:
                with transaction.atomic():
                    invoice.total_amount = new_total
                    invoice.save()
                    for deleted_item in formset.deleted_objects:
                        deleted_item.delete()
                    for item in items:
                        item.invoice = invoice
                        item.save()
                    formset.save_m2m()
                    invoice.update_status()
                messages.success(request, "Invoice updated successfully.")
                return redirect('finance:invoice_list')
    else:
        invoice_form = InvoiceForm(instance=invoice)
        formset = InvoiceItemFormSet(instance=invoice)

    return render(request, 'finance/edit_invoice.html', {
        'invoice': invoice,
        'invoice_form': invoice_form,
        'formset': formset
    })

@login_required
def student_invoices(request):
    if not request.user.is_student:
        return HttpResponseForbidden("You are not authorized to view this page.")
    invoices = Invoice.objects.filter(
        student__student=request.user,
    ).select_related("semester").prefetch_related("items__category", "payments")
    return render(request, 'finance/view_student_invoices.html', {'invoices': invoices})

@login_required
def student_invoice_detail(request, invoice_id):
    if not request.user.is_student:
        return HttpResponseForbidden("You are not authorized to view this invoice.")
    invoice = get_object_or_404(
        Invoice.objects.prefetch_related("items__category", "payments"),
        id=invoice_id,
        student__student=request.user,
    )
    items = InvoiceItem.objects.filter(invoice=invoice)
    balance = invoice.total_amount - invoice.paid_amount
    payment_currency = settings.ONLINE_PAYMENT_CURRENCY
    currency_configured = (
        len(payment_currency) == 3
        and payment_currency.isascii()
        and payment_currency.isalpha()
    )

    return render(request, 'finance/student_invoice_detail.html', {
        'invoice': invoice,
        'items': items,
        'balance': balance,
        'stripe_available': bool(settings.STRIPE_SECRET_KEY and currency_configured),
        'paypal_available': bool(
            settings.PAYPAL_CLIENT_ID
            and settings.PAYPAL_CLIENT_SECRET
            and currency_configured
        ),
        'pending_online_payment': invoice.online_payment_attempts.filter(
            status=OnlineInvoicePayment.Status.PENDING,
        ).first(),
    })


@login_required
@require_POST
def start_online_invoice_payment(request, invoice_id, provider):
    if not request.user.is_student:
        return HttpResponseForbidden("Only students can pay their own invoices.")
    if provider not in OnlineInvoicePayment.Provider.values:
        return HttpResponseForbidden("The selected payment provider is not supported.")

    invoice = get_object_or_404(
        Invoice,
        pk=invoice_id,
        student__student=request.user,
    )
    currency = settings.ONLINE_PAYMENT_CURRENCY
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        messages.error(request, "Online payment currency is not configured correctly.")
        return redirect("finance:view_student_invoice", invoice_id=invoice.pk)

    try:
        attempt, _created = create_online_invoice_payment(
            invoice_id=invoice.pk,
            provider=provider,
            currency=currency,
        )
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("finance:view_student_invoice", invoice_id=invoice.pk)
    except IntegrityError:
        messages.error(
            request,
            "Another online payment is being started for this invoice. Please try again.",
        )
        return redirect("finance:view_student_invoice", invoice_id=invoice.pk)

    if attempt.provider != provider:
        messages.error(request, "A different online payment is already pending.")
        return redirect("finance:view_student_invoice", invoice_id=invoice.pk)
    if attempt.provider_redirect_url:
        return redirect(attempt.provider_redirect_url)

    invoice_url = reverse("finance:view_student_invoice", args=(invoice.pk,))
    if provider == OnlineInvoicePayment.Provider.STRIPE:
        success_url = request.build_absolute_uri(
            reverse("finance:stripe_payment_success")
        )
        success_url += f"?attempt={attempt.pk}&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = request.build_absolute_uri(invoice_url)
        cancel_url += f"?payment_cancelled={attempt.pk}"
        try:
            session = create_stripe_checkout(attempt, success_url, cancel_url)
        except PaymentProviderError as error:
            attempt.status = OnlineInvoicePayment.Status.FAILED
            attempt.save(update_fields=("status", "updated_at"))
            messages.error(request, str(error))
            return redirect("finance:view_student_invoice", invoice_id=invoice.pk)
        attempt.provider_session_id = session.id
        attempt.provider_redirect_url = session.url
    else:
        return_url = request.build_absolute_uri(
            reverse("finance:paypal_payment_return")
        )
        return_url += f"?attempt={attempt.pk}"
        cancel_url = request.build_absolute_uri(invoice_url)
        cancel_url += f"?payment_cancelled={attempt.pk}"
        try:
            order_id, approval_url = create_paypal_order(
                attempt,
                return_url,
                cancel_url,
            )
        except PaymentProviderError as error:
            attempt.status = OnlineInvoicePayment.Status.FAILED
            attempt.save(update_fields=("status", "updated_at"))
            messages.error(request, str(error))
            return redirect("finance:view_student_invoice", invoice_id=invoice.pk)
        attempt.provider_session_id = order_id
        attempt.provider_redirect_url = approval_url

    attempt.save(
        update_fields=(
            "provider_session_id",
            "provider_redirect_url",
            "updated_at",
        )
    )
    return redirect(attempt.provider_redirect_url)


@login_required
def stripe_payment_success(request):
    if not request.user.is_student:
        return HttpResponseForbidden("Only students can confirm their online payments.")
    attempt = get_object_or_404(
        OnlineInvoicePayment.objects.select_related("invoice"),
        pk=request.GET.get("attempt"),
        provider=OnlineInvoicePayment.Provider.STRIPE,
        invoice__student__student=request.user,
    )
    session_id = request.GET.get("session_id", "")
    if not session_id or session_id != attempt.provider_session_id:
        return HttpResponseForbidden("The Stripe checkout session does not match.")
    if attempt.status == OnlineInvoicePayment.Status.SUCCEEDED:
        return redirect(
            "finance:view_student_invoice",
            invoice_id=attempt.invoice_id,
        )

    try:
        session = retrieve_stripe_checkout(session_id)
        metadata = session.metadata or {}
        if (
            session.id != attempt.provider_session_id
            or session.status != "complete"
            or session.payment_status != "paid"
            or session.client_reference_id != str(attempt.pk)
            or metadata.get("attempt_id") != str(attempt.pk)
            or metadata.get("invoice_id") != str(attempt.invoice_id)
            or session.amount_total != int(attempt.amount * 100)
            or not isinstance(session.currency, str)
            or session.currency.lower() != attempt.currency.lower()
        ):
            messages.error(request, "Stripe has not confirmed this invoice payment.")
            return redirect(
                "finance:view_student_invoice",
                invoice_id=attempt.invoice_id,
            )
        provider_reference = str(session.payment_intent or session.id)
        finalize_online_invoice_payment(
            attempt_id=attempt.pk,
            provider_reference=provider_reference,
            method=InvoicePayment.Method.CARD,
        )
    except (PaymentProviderError, ValueError) as error:
        messages.error(request, str(error))
        return redirect(
            "finance:view_student_invoice",
            invoice_id=attempt.invoice_id,
        )

    messages.success(request, "Your invoice payment has been confirmed.")
    return redirect("finance:view_student_invoice", invoice_id=attempt.invoice_id)


@login_required
def paypal_payment_return(request):
    if not request.user.is_student:
        return HttpResponseForbidden("Only students can confirm their online payments.")
    attempt = get_object_or_404(
        OnlineInvoicePayment.objects.select_related("invoice"),
        pk=request.GET.get("attempt"),
        provider=OnlineInvoicePayment.Provider.PAYPAL,
        invoice__student__student=request.user,
    )
    order_id = request.GET.get("token", "")
    if not order_id or order_id != attempt.provider_session_id:
        return HttpResponseForbidden("The PayPal order does not match this invoice.")
    if attempt.status == OnlineInvoicePayment.Status.SUCCEEDED:
        return redirect(
            "finance:view_student_invoice",
            invoice_id=attempt.invoice_id,
        )

    try:
        response = capture_paypal_order(
            order_id,
            str(attempt.idempotency_key),
        )
        purchase_units = response.get("purchase_units", [])
        capture = {}
        purchase_unit = {}
        if (
            isinstance(purchase_units, list)
            and purchase_units
            and isinstance(purchase_units[0], dict)
        ):
            purchase_unit = purchase_units[0]
            payment_data = purchase_unit.get("payments") or {}
            captures = payment_data.get("captures", [])
            if isinstance(captures, list) and captures and isinstance(captures[0], dict):
                capture = captures[0]
        capture_amount = capture.get("amount") or {}
        if (
            response.get("status") != "COMPLETED"
            or purchase_unit.get("custom_id") != str(attempt.pk)
            or capture.get("status") != "COMPLETED"
            or capture_amount.get("currency_code") != attempt.currency
            or capture_amount.get("value") != f"{attempt.amount:.2f}"
            or not capture.get("id")
        ):
            messages.error(request, "PayPal has not confirmed this invoice payment.")
            return redirect(
                "finance:view_student_invoice",
                invoice_id=attempt.invoice_id,
            )
        finalize_online_invoice_payment(
            attempt_id=attempt.pk,
            provider_reference=capture["id"],
            method=InvoicePayment.Method.PAYPAL,
        )
    except (PaymentProviderError, ValueError) as error:
        messages.error(request, str(error))
        return redirect(
            "finance:view_student_invoice",
            invoice_id=attempt.invoice_id,
        )

    messages.success(request, "Your invoice payment has been confirmed.")
    return redirect("finance:view_student_invoice", invoice_id=attempt.invoice_id)


# @login_required
# def student_invoice_detail(request, invoice_id):
#     invoice = get_object_or_404(Invoice, id=invoice_id, student=request.user.student)
#     items = InvoiceItem.objects.filter(invoice=invoice)
#     balance = invoice.total_amount - invoice.paid_amount

#     return render(request, 'finance/student_invoice_detail.html', {
#         'invoice': invoice,
#         'items': items,
#         'balance': balance
#     })

@login_required
@finance_permission_required("manage_invoices")
def fee_category_list(request):
    categories = FeeCategory.objects.annotate(
        has_invoice_items=Exists(
            InvoiceItem.objects.filter(category_id=OuterRef("pk"))
        )
    )
    return render(request, 'finance/manage_fee_categories.html', {
        'categories': categories,
        'can_add_categories': has_finance_action_permission(
            request.user,
            "finance.fee_category.add",
            "manage_fee_categories",
            "fee_category_add",
        ),
        'can_edit_categories': has_finance_action_permission(
            request.user,
            "finance.fee_category.edit",
            "manage_fee_categories",
            "fee_category_add",
        ),
        'can_delete_categories': has_finance_action_permission(
            request.user,
            "finance.fee_category.delete",
            "manage_fee_categories",
            "fee_category_add",
        ),
    })


@login_required
@finance_action_permission_required(
    "finance.fee_category.add",
    "manage_fee_categories",
    "fee_category_add",
)
def fee_category_add(request):
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    
    if request.method == 'POST':
        form = FeeCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:fee_category_list')
    else:
        form = FeeCategoryForm(initial={'semester': current_semester})

    return render(request, 'finance/fee_category_add.html', {'form': form})


@login_required
@finance_action_permission_required(
    "finance.fee_category.edit",
    "manage_fee_categories",
    "fee_category_add",
)
def fee_category_edit(request, category_id):
    category = get_object_or_404(FeeCategory, pk=category_id)

    if request.method == 'POST':
        form = FeeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Fee category updated.")
            return redirect('finance:fee_category_list')
    else:
        form = FeeCategoryForm(instance=category)

    return render(request, 'finance/fee_category_add.html', {
        'form': form,
        'category': category,
        'title': "Edit Fee Category",
    })


@login_required
@finance_action_permission_required(
    "finance.fee_category.delete",
    "manage_fee_categories",
    "fee_category_add",
)
@require_POST
def fee_category_delete(request, category_id):
    category = get_object_or_404(FeeCategory, pk=category_id)
    if InvoiceItem.objects.filter(category=category).exists():
        messages.warning(
            request,
            "This fee category cannot be deleted because it is used by existing invoices.",
        )
    else:
        category.delete()
        messages.success(request, "Fee category deleted.")
    return redirect("finance:fee_category_list")


@login_required
@finance_permission_required("create_invoice", "manage_invoices")
def generate_semester_invoices(request):
    semester = get_object_or_404(Semester, is_current_semester=True)
    if request.method == "POST":
        form = SemesterInvoiceGenerationForm(request.POST)
        if form.is_valid():
            created_count = create_semester_invoices(
                semester,
                form.cleaned_data["due_date"],
            )
            messages.success(
                request,
                f"Created {created_count} invoice(s) for {semester}. "
                "Existing student invoices were left unchanged.",
            )
            return redirect("finance:invoice_list")
    else:
        form = SemesterInvoiceGenerationForm(
            initial={"due_date": timezone.localdate()}
        )
    return render(
        request,
        "finance/generate_semester_invoices.html",
        {"form": form, "semester": semester},
    )


@login_required
@finance_permission_required("manage_invoices")
@require_POST
def record_invoice_payment_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    form = InvoicePaymentForm(request.POST)
    if form.is_valid():
        payment_data = form.cleaned_data
        try:
            record_invoice_payment(
                invoice_id=invoice.pk,
                amount=payment_data["amount"],
                payment_date=payment_data["payment_date"],
                method=payment_data["method"],
                reference=payment_data["reference"],
                user=request.user,
            )
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Payment recorded successfully.")
    else:
        messages.error(request, "Enter valid payment details.")
    return redirect("finance:view_invoice", invoice_id=invoice.pk)


@login_required
@finance_permission_required("staff_category_list")
def staff_category_list(request):
    categories = StaffCategory.objects.all()
    return render(request, 'finance/staff_category_list.html', {'categories': categories})


@login_required
@finance_permission_required("staff_manage")
def staff_category_add(request):
    if request.method == 'POST':
        form = StaffCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:staff_category_list')
    else:
        form = StaffCategoryForm()

    return render(request, 'finance/staff_category_add.html', {'form': form})


@login_required
@finance_permission_required("staff_list")
def staff_list(request):
    staff_members = Staff.objects.select_related(
        'user',
        'category',
        'department',
    ).all()
    return render(
        request,
        'finance/staff_list.html',
        {
            'staff_members': staff_members,
            'can_manage_staff': has_finance_permission(request.user, "staff_manage"),
            'can_view_departments': has_finance_permission(request.user, "department_list"),
        },
    )


@login_required
@finance_permission_required("staff_manage")
def staff_add(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:staff_list')
    else:
        form = StaffForm()

    return render(request, 'finance/staff_add.html', {'form': form})


@login_required
@finance_permission_required("payroll_list")
def payroll_list(request):
    payrolls = Payroll.objects.select_related('staff__user').all()
    return render(request, 'finance/payroll_list.html', {'payrolls': payrolls})


@login_required
@finance_permission_required("payroll_list")
def payroll_add(request):
    if request.method == 'POST':
        form = PayrollForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:payroll_list')
    else:
        form = PayrollForm()

    return render(request, 'finance/payroll_add.html', {'form': form})


@login_required
@finance_permission_required("expense_category_list")
def expense_category_list(request):
    categories = ExpenseCategory.objects.all()
    return render(request, 'finance/expense_category_list.html', {'categories': categories})


@login_required
@finance_permission_required("expense_category_list")
def expense_category_add(request):
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:expense_category_list')
    else:
        form = ExpenseCategoryForm()

    return render(
        request,
        'finance/expense_category_add.html',
        {'form': form, 'title': "Add Expense Category"},
    )

@login_required
@finance_permission_required("expense_category_list")
def expense_category_edit(request, category_id):
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense category updated.")
            return redirect('finance:expense_category_list')
    else:
        form = ExpenseCategoryForm(instance=category)

    return render(
        request,
        'finance/expense_category_add.html',
        {
            'form': form,
            'category': category,
            'title': "Edit Expense Category",
        },
    )

@login_required
@finance_permission_required("expense_list")
def expense_list(request):
    expenses = Expense.objects.select_related('category', 'paid_by').all()
    return render(request, 'finance/expense_list.html', {'expenses': expenses})


@login_required
@finance_permission_required("expense_list")
def expense_add(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:expense_list')
    else:
        form = ExpenseForm()

    return render(request, 'finance/expense_add.html', {'form': form})


@login_required
@finance_permission_required("petty_cash_list")
def petty_cash_list(request):
    entries = PettyCashEntry.objects.select_related('created_by').all()
    return render(request, 'finance/petty_cash_list.html', {'entries': entries})


@login_required
@finance_permission_required("petty_cash_list")
def petty_cash_add(request):
    if request.method == 'POST':
        form = PettyCashEntryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:petty_cash_list')
    else:
        form = PettyCashEntryForm()

    return render(request, 'finance/petty_cash_add.html', {'form': form})


@login_required
@finance_permission_required("accounts_payable_list")
def accounts_payable_list(request):
    payables = AccountPayable.objects.all()
    return render(request, 'finance/accounts_payable_list.html', {'payables': payables})


@login_required
@finance_permission_required("accounts_payable_list")
def accounts_payable_add(request):
    if request.method == 'POST':
        form = AccountPayableForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:accounts_payable_list')
    else:
        form = AccountPayableForm()

    return render(request, 'finance/accounts_payable_add.html', {'form': form})


@login_required
@finance_permission_required("accounts_receivable_list")
def accounts_receivable_list(request):
    receivables = AccountReceivable.objects.all()
    return render(request, 'finance/accounts_receivable_list.html', {'receivables': receivables})


@login_required
@finance_permission_required("accounts_receivable_list")
def accounts_receivable_add(request):
    if request.method == 'POST':
        form = AccountReceivableForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance:accounts_receivable_list')
    else:
        form = AccountReceivableForm()

    return render(request, 'finance/accounts_receivable_add.html', {'form': form})


@login_required
@finance_permission_required("budget_list")
def budget_list(request):
    budgets = Budget.objects.select_related('requested_by', 'approved_by').order_by('-created_at')
    return render(request, 'finance/budget_list.html', {'budgets': budgets})


@login_required
@finance_permission_required("budget_list")
def budget_add(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            if budget.approved and not budget.approved_at:
                budget.approved_at = timezone.now()
            budget.save()
            messages.success(request, 'Budget request created successfully.')
            return redirect('finance:budget_list')
    else:
        form = BudgetForm()

    return render(request, 'finance/budget_add.html', {'form': form})


@login_required
@finance_permission_required("cash_book_list")
def cash_book_list(request):
    entries = CashBookEntry.objects.select_related('created_by').order_by('-date')
    return render(request, 'finance/cash_book_list.html', {'entries': entries})


@login_required
@finance_permission_required("cash_book_list")
def cash_book_add(request):
    if request.method == 'POST':
        form = CashBookEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cash book entry created successfully.')
            return redirect('finance:cash_book_list')
    else:
        form = CashBookEntryForm()

    return render(request, 'finance/cash_book_add.html', {'form': form})


@login_required
@finance_permission_required("bank_reconciliation_list")
def bank_reconciliation_list(request):
    reconciliations = BankReconciliation.objects.select_related('reconciled_by').order_by('-statement_date')
    return render(request, 'finance/bank_reconciliation_list.html', {'reconciliations': reconciliations})


@login_required
@finance_permission_required("bank_reconciliation_list")
def bank_reconciliation_add(request):
    if request.method == 'POST':
        form = BankReconciliationForm(request.POST)
        if form.is_valid():
            reconciliation = form.save(commit=False)
            if reconciliation.reconciled and not reconciliation.reconciled_at:
                reconciliation.reconciled_at = timezone.now()
            reconciliation.save()
            messages.success(request, 'Bank reconciliation saved successfully.')
            return redirect('finance:bank_reconciliation_list')
    else:
        form = BankReconciliationForm()

    return render(request, 'finance/bank_reconciliation_add.html', {'form': form})


@login_required
@finance_permission_required("ledger_account_list")
def ledger_account_list(request):
    accounts = LedgerAccount.objects.all().order_by('code')
    return render(request, 'finance/ledger_account_list.html', {'accounts': accounts})


@login_required
@finance_permission_required("ledger_account_list")
def ledger_account_add(request):
    if request.method == 'POST':
        form = LedgerAccountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ledger account created successfully.')
            return redirect('finance:ledger_account_list')
    else:
        form = LedgerAccountForm()

    return render(request, 'finance/ledger_account_add.html', {'form': form})


@login_required
@finance_permission_required("general_ledger_list")
def general_ledger_list(request):
    entries = GeneralLedgerEntry.objects.select_related('account', 'created_by').order_by('-date')
    return render(request, 'finance/general_ledger_list.html', {'entries': entries})


@login_required
@finance_permission_required("general_ledger_list")
def general_ledger_add(request):
    if request.method == 'POST':
        form = GeneralLedgerEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'General ledger entry created successfully.')
            return redirect('finance:general_ledger_list')
    else:
        form = GeneralLedgerEntryForm()

    return render(request, 'finance/general_ledger_add.html', {'form': form})


@login_required
@finance_permission_required("payment_voucher_list")
def payment_voucher_list(request):
    vouchers = PaymentVoucher.objects.select_related('requested_by', 'approved_by').order_by('-created_at')
    return render(request, 'finance/payment_voucher_list.html', {'vouchers': vouchers})


@login_required
@finance_permission_required("payment_voucher_list")
def payment_voucher_add(request):
    if request.method == 'POST':
        form = PaymentVoucherForm(request.POST)
        if form.is_valid():
            voucher = form.save(commit=False)
            if voucher.approved and not voucher.approved_at:
                voucher.approved_at = timezone.now()
            voucher.save()
            messages.success(request, 'Payment voucher created successfully.')
            return redirect('finance:payment_voucher_list')
    else:
        form = PaymentVoucherForm()

    return render(request, 'finance/payment_voucher_add.html', {'form': form})


@login_required
@finance_permission_required("finance_reports")
def finance_reports(request):
    invoice_totals = Invoice.objects.aggregate(
        total=Sum("total_amount"),
        paid=Sum("paid_amount"),
    )
    payables_total = AccountPayable.objects.filter(paid=False).aggregate(
        total=Sum("amount"),
    )["total"]
    receivables_total = AccountReceivable.objects.filter(received=False).aggregate(
        total=Sum("amount"),
    )["total"]
    cash_totals = CashBookEntry.objects.aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )
    total_budgets = Budget.objects.count()
    total_cash_entries = CashBookEntry.objects.count()
    total_reconciliations = BankReconciliation.objects.count()
    total_ledger_accounts = LedgerAccount.objects.count()
    total_ledger_entries = GeneralLedgerEntry.objects.count()
    total_vouchers = PaymentVoucher.objects.count()
    total_payables = AccountPayable.objects.filter(paid=False).count()
    total_receivables = AccountReceivable.objects.filter(received=False).count()

    context = {
        'total_budgets': total_budgets,
        'total_cash_entries': total_cash_entries,
        'total_reconciliations': total_reconciliations,
        'total_ledger_accounts': total_ledger_accounts,
        'total_ledger_entries': total_ledger_entries,
        'total_vouchers': total_vouchers,
        'total_payables': total_payables,
        'total_receivables': total_receivables,
        'budget_amount': Budget.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        'invoice_total': invoice_totals["total"] or Decimal("0.00"),
        'invoice_paid': invoice_totals["paid"] or Decimal("0.00"),
        'invoice_outstanding': (
            (invoice_totals["total"] or Decimal("0.00"))
            - (invoice_totals["paid"] or Decimal("0.00"))
        ),
        'open_payables_amount': payables_total or Decimal("0.00"),
        'open_receivables_amount': receivables_total or Decimal("0.00"),
        'cash_debits': cash_totals["debit"] or Decimal("0.00"),
        'cash_credits': cash_totals["credit"] or Decimal("0.00"),
    }
    return render(request, 'finance/finance_reports.html', context)


@login_required
@admin_required
def assign_finance_modules(request):
    finance_users = User.objects.filter(is_finance=True)
    existing_permissions = FinanceModulePermission.objects.all()

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        module = request.POST.get("module_name")

        user = get_object_or_404(User, id=user_id, is_finance=True)

        if not FinanceModulePermission.objects.filter(staff=user, module_name=module).exists():
            FinanceModulePermission.objects.create(staff=user, module_name=module)
            messages.success(request, f"{module} assigned to {user.get_full_name}.")
        else:
            messages.warning(request, "Module already assigned.")

    # Use the configured module choices from the FinanceModulePermission model
    module_choices = FinanceModulePermission._meta.get_field('module_name').choices

    return render(request, "finance/assign_finance_module.html", {
        "finance_users": finance_users,
        "existing_permissions": existing_permissions,
        "module_choices": module_choices,
    })


@login_required
def view_student_invoice(request, invoice_id):
    return student_invoice_detail(request, invoice_id)


@login_required
@finance_permission_required("staff_manage")
def staff_edit(request, staff_id):
    staff_member = get_object_or_404(
        Staff.objects.select_related('user'),
        pk=staff_id,
    )
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff_member)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff record updated.")
            return redirect('finance:staff_list')
    else:
        form = StaffForm(instance=staff_member)
    return render(
        request,
        'finance/staff_add.html',
        {
            'form': form,
            'staff_member': staff_member,
        },
    )


@login_required
@finance_permission_required("department_list")
def staff_department_list(request):
    departments = StaffDepartment.objects.select_related(
        'faculty',
        'head',
    ).all()
    return render(
        request,
        'finance/staff_department_list.html',
        {
            'departments': departments,
            'can_manage_departments': has_finance_permission(
                request.user,
                "department_manage",
            ),
        },
    )


@login_required
@finance_permission_required("department_manage")
def staff_department_add(request):
    if request.method == 'POST':
        form = StaffDepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Department created.")
            return redirect('finance:staff_department_list')
    else:
        form = StaffDepartmentForm()
    return render(
        request,
        'finance/staff_department_form.html',
        {'form': form, 'title': "Add Department"},
    )


@login_required
@finance_permission_required("department_manage")
def staff_department_edit(request, department_id):
    department = get_object_or_404(StaffDepartment, pk=department_id)
    if request.method == 'POST':
        form = StaffDepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, "Department updated.")
            return redirect('finance:staff_department_list')
    else:
        form = StaffDepartmentForm(instance=department)
    return render(
        request,
        'finance/staff_department_form.html',
        {
            'form': form,
            'department': department,
            'title': "Edit Department",
        },
    )


@login_required
@finance_permission_required("manage_invoices")
def invoice_detail(request, invoice_id):
    invoice = get_object_or_404(
        Invoice.objects.select_related("student__student", "semester")
        .prefetch_related("items__category", "payments__recorded_by"),
        id=invoice_id,
    )
    balance = invoice.total_amount - invoice.paid_amount
    return render(request, 'finance/invoice_detail.html', {
        'invoice': invoice,
        'balance': balance,
        'payment_form': InvoicePaymentForm(
            initial={"payment_date": timezone.localdate()}
        ),
    })

@login_required
@finance_permission_required("manage_invoices")
def view_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    items = InvoiceItem.objects.filter(invoice=invoice)
    balance = invoice.total_amount - invoice.paid_amount
    return render(request, 'finance/view_invoice.html', {
        'invoice': invoice,
        'items': items,
        'balance': balance
    })

@login_required
@finance_permission_required("manage_invoices")
def export_invoice_table_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Student Name", "Registration #", "Invoice #", "Semester",
        "Categories", "Total", "Paid", "Balance", "Status", "Date Issued"
    ])

    invoices = Invoice.objects.select_related('student__student', 'semester').prefetch_related('items__category')

    for invoice in invoices:
        categories = ", ".join([item.category.name for item in invoice.items.all()])
        writer.writerow([
            invoice.student.student.get_full_name,
            invoice.student.registration_number,
            f"INV{invoice.id:05d}",
            invoice.semester.get_semester_display(),
            categories,
            invoice.total_amount,
            invoice.paid_amount,
            invoice.balance,
            invoice.status,
            invoice.date_issued.strftime("%d %b %Y")
        ])

    return response

@login_required
@finance_permission_required("manage_invoices")
def export_invoice_table_pdf(request):
    invoices = Invoice.objects.all().select_related('student__student', 'semester').prefetch_related('items__category')
    template = get_template("finance/pdf/invoice_table.html")
    logo_url = request.build_absolute_uri(static('img/logo.png'))

    html = template.render({
        "invoices": invoices,
        "logo_url": logo_url,
        "site_settings": SiteSettings.get_settings(),
        "school_name": SiteSettings.get_settings().school_name,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="invoice_table.pdf"'

    pisa_status = pisa.CreatePDF(
        io.BytesIO(html.encode("UTF-8")),
        dest=response,
        link_callback=pdf_link_callback,
    )
    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)
    return response

@login_required
@admin_required
@require_POST
def revoke_finance_module(request, permission_id):
    permission = get_object_or_404(FinanceModulePermission, id=permission_id)
    permission.delete()
    messages.success(request, "Finance module access revoked.")
    return redirect('finance:assign_finance_modules')
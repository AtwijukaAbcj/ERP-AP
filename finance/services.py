from decimal import Decimal
import logging

from django.db import transaction
from django.utils import timezone

from accounts.models import Student

from .models import (
    FeeCategory,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    OnlineInvoicePayment,
)


logger = logging.getLogger(__name__)


@transaction.atomic
def create_semester_invoices(semester, due_date):
    categories = list(FeeCategory.objects.filter(semester=semester).order_by("pk"))
    if not categories:
        return 0

    existing_student_ids = set(
        Invoice.objects.filter(semester=semester).values_list("student_id", flat=True)
    )
    students = Student.objects.filter(
        status=Student.Status.ACTIVE,
        student__is_active=True,
        student__is_student=True,
    ).select_related("student").order_by("pk")
    created_count = 0

    for student in students:
        if student.pk in existing_student_ids:
            continue
        student_categories = [
            category
            for category in categories
            if category.student_id is None or category.student_id == student.pk
        ]
        if not student_categories:
            continue

        total_amount = sum(
            (category.amount for category in student_categories),
            Decimal("0.00"),
        )
        invoice = Invoice.objects.create(
            student=student,
            semester=semester,
            due_date=due_date,
            total_amount=total_amount,
        )
        InvoiceItem.objects.bulk_create(
            [
                InvoiceItem(
                    invoice=invoice,
                    category=category,
                    amount=category.amount,
                )
                for category in student_categories
            ]
        )
        created_count += 1

    return created_count


@transaction.atomic
def record_invoice_payment(*, invoice_id, amount, payment_date, method, reference, user):
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
    if amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")
    if amount > invoice.balance:
        raise ValueError("Payment amount cannot exceed the outstanding balance.")

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        amount=amount,
        payment_date=payment_date,
        method=method,
        reference=reference,
        recorded_by=user,
    )
    invoice.paid_amount += amount
    invoice.update_status()
    return payment


@transaction.atomic
def create_online_invoice_payment(*, invoice_id, provider, currency):
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
    if invoice.balance <= Decimal("0.00"):
        raise ValueError("This invoice has no outstanding balance.")

    pending_attempt = OnlineInvoicePayment.objects.filter(
        invoice=invoice,
        status=OnlineInvoicePayment.Status.PENDING,
    ).first()
    if pending_attempt:
        if pending_attempt.provider == provider:
            return pending_attempt, False
        raise ValueError(
            "An online payment is already pending for this invoice. Resume or complete it first."
        )

    attempt = OnlineInvoicePayment.objects.create(
        invoice=invoice,
        provider=provider,
        amount=invoice.balance,
        currency=currency,
    )
    return attempt, True


@transaction.atomic
def finalize_online_invoice_payment(*, attempt_id, provider_reference, method):
    attempt = OnlineInvoicePayment.objects.select_for_update().get(pk=attempt_id)
    if attempt.status == OnlineInvoicePayment.Status.SUCCEEDED:
        if attempt.provider_reference != provider_reference:
            raise ValueError("The payment attempt was already completed with another reference.")
        return attempt.invoice_payment
    if attempt.status != OnlineInvoicePayment.Status.PENDING:
        raise ValueError("This online payment attempt is not pending.")
    if not provider_reference:
        raise ValueError("The payment provider did not return a transaction reference.")

    invoice = Invoice.objects.select_for_update().get(pk=attempt.invoice_id)
    if attempt.amount > invoice.balance:
        logger.error(
            "Verified online payment for invoice %s exceeds its remaining balance; "
            "provider reference %s requires reconciliation.",
            invoice.pk,
            provider_reference,
        )
        raise ValueError(
            "The payment was confirmed, but the invoice balance changed during checkout. "
            "Contact the finance office with the provider transaction reference."
        )

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        amount=attempt.amount,
        payment_date=timezone.localdate(),
        method=method,
        reference=f"{attempt.provider}:{provider_reference}",
    )
    invoice.paid_amount += attempt.amount
    invoice.update_status()
    attempt.status = OnlineInvoicePayment.Status.SUCCEEDED
    attempt.provider_reference = provider_reference
    attempt.invoice_payment = payment
    attempt.save(
        update_fields=(
            "status",
            "provider_reference",
            "invoice_payment",
            "updated_at",
        )
    )
    return payment

import csv
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from accounts.models import Student, User
from admissions.models import Application
from clinical.models import ClinicalPlacement
from course.models import Course, Upload, UploadVideo
from finance.models import Invoice, PaymentVoucher, Staff
from procurement.models import PurchaseOrder, PurchaseRequisition
from result.models import AttendanceRecord, CourseAssignment, TakenCourse

from .models import Semester, SiteSettings
from .pdf_utils import pdf_link_callback


logger = logging.getLogger(__name__)
REPORT_PERMISSION = "reports.view"


def user_can_view_reports(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if user.permission_overrides.filter(
        permission__code=REPORT_PERMISSION,
        effect="deny",
    ).exists():
        return False
    return user.has_permission(REPORT_PERMISSION) or user.can_access_module("reports")


def _report_data(semester):
    students = Student.objects.all()
    applications = Application.objects.all()
    enrollments = TakenCourse.objects.all()
    placements = ClinicalPlacement.objects.all()
    invoices = Invoice.objects.all()
    if semester:
        enrollments = enrollments.filter(semester=semester)
        placements = placements.filter(semester=semester)
        invoices = invoices.filter(semester=semester)
        if semester.session_id:
            applications = applications.filter(
                academic_year=semester.session.session,
            )

    course_performance = list(
        enrollments.values("course__code", "course__title")
        .annotate(
            enrollment_count=Count("pk"),
            average_score=Avg("total"),
        )
        .order_by("course__code")
    )
    attendance_by_status = list(
        AttendanceRecord.objects.values("status")
        .annotate(count=Count("pk"))
        .order_by("status")
    )
    attendance_total = sum(item["count"] for item in attendance_by_status)
    attendance_present = sum(
        item["count"]
        for item in attendance_by_status
        if item["status"] in {"present", "late"}
    )
    lecturers_by_qualification = list(
        Staff.objects.filter(user__is_lecturer=True, user__is_active=True)
        .values("qualification")
        .annotate(count=Count("pk"))
        .order_by("qualification")
    )

    grade_stats = enrollments.aggregate(
        average_score=Avg("total"),
        pass_count=Count("id", filter=Q(comment="PASS")),
        fail_count=Count("id", filter=Q(comment="FAIL")),
    )
    finance_stats = invoices.aggregate(
        invoice_total=Sum("total_amount"),
        amount_paid=Sum("paid_amount"),
        outstanding=Sum("total_amount") - Sum("paid_amount"),
    )
    procurement_stats = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
        approved=True,
    ).aggregate(
        approved_order_count=Count("id"),
        approved_order_total=Sum("total_amount"),
    )

    return {
        "generated_at": timezone.localtime(),
        "semester": semester,
        "semesters": Semester.objects.select_related("session").order_by(
            "-session__session",
            "semester",
        ),
        "student_count": students.count(),
        "active_student_count": students.filter(
            status=Student.Status.ACTIVE,
        ).count(),
        "admission_total": applications.count(),
        "admissions_by_status": list(
            applications.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        ),
        "lecturer_count": User.objects.filter(
            is_lecturer=True,
            is_active=True,
        ).count(),
        "active_enrollment_count": enrollments.count(),
        "dropped_enrollment_count": (
            TakenCourse.all_objects.filter(semester=semester, is_dropped=True).count()
            if semester
            else TakenCourse.all_objects.filter(is_dropped=True).count()
        ),
        "average_score": grade_stats["average_score"] or Decimal("0.00"),
        "pass_count": grade_stats["pass_count"],
        "fail_count": grade_stats["fail_count"],
        "clinical_placement_count": placements.count(),
        "active_clinical_placement_count": placements.filter(
            status=ClinicalPlacement.Status.IN_PROGRESS,
        ).count(),
        "invoice_count": invoices.count(),
        "invoice_total": finance_stats["invoice_total"] or Decimal("0.00"),
        "amount_paid": finance_stats["amount_paid"] or Decimal("0.00"),
        "outstanding": finance_stats["outstanding"] or Decimal("0.00"),
        "approved_order_count": procurement_stats["approved_order_count"],
        "approved_order_total": (
            procurement_stats["approved_order_total"] or Decimal("0.00")
        ),
        "open_requisition_count": PurchaseRequisition.objects.filter(
            deleted_at__isnull=True,
        ).filter(
            Q(status__isnull=True)
            | ~Q(status__slug__in=("approved", "rejected", "completed", "cancelled"))
        ).count(),
        "pending_voucher_count": PaymentVoucher.objects.filter(
            approved=False,
        ).count(),
        "students_by_program": list(
            students.values("program__title")
            .annotate(count=Count("id"))
            .order_by("program__title")
        ),
        "students_by_level": list(
            students.values("level").annotate(count=Count("pk")).order_by("level")
        ),
        "lecturers_by_qualification": lecturers_by_qualification,
        "course_performance": course_performance,
        "attendance_by_status": attendance_by_status,
        "attendance_total": attendance_total,
        "attendance_rate": (
            round(attendance_present / attendance_total * 100, 2)
            if attendance_total
            else Decimal("0.00")
        ),
        "course_resource_counts": {
            "courses": Course.objects.count(),
            "documents": Upload.objects.count(),
            "videos": UploadVideo.objects.count(),
            "assignments": CourseAssignment.objects.count(),
        },
    }


def _resolve_semester(request):
    semester_id = request.GET.get("semester")
    if semester_id:
        return get_object_or_404(Semester.objects.select_related("session"), pk=semester_id)
    return Semester.objects.select_related("session").filter(
        is_current_semester=True,
    ).first()


@login_required
def institutional_reports(request):
    if not user_can_view_reports(request.user):
        raise PermissionDenied
    semester = _resolve_semester(request)
    context = _report_data(semester)
    return render(request, "core/institutional_reports.html", context)


@login_required
def export_institutional_report_csv(request):
    if not user_can_view_reports(request.user):
        raise PermissionDenied
    semester = _resolve_semester(request)
    data = _report_data(semester)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="institutional-report.csv"'
    writer = csv.writer(response)
    writer.writerow(("Metric", "Value"))
    writer.writerow(("Report generated", data["generated_at"].isoformat()))
    writer.writerow(("Academic period", str(semester) if semester else "All periods"))
    for label, key in (
        ("Total students", "student_count"),
        ("Active students", "active_student_count"),
        ("Applications", "admission_total"),
        ("Lecturers", "lecturer_count"),
        ("Active course enrollments", "active_enrollment_count"),
        ("Dropped course enrollments", "dropped_enrollment_count"),
        ("Average result score", "average_score"),
        ("Passing results", "pass_count"),
        ("Failing results", "fail_count"),
        ("Clinical placements", "clinical_placement_count"),
        ("Active clinical placements", "active_clinical_placement_count"),
        ("Invoices", "invoice_count"),
        ("Invoice total", "invoice_total"),
        ("Payments recorded", "amount_paid"),
        ("Outstanding invoice balance", "outstanding"),
        ("Approved purchase orders", "approved_order_count"),
        ("Approved purchase order total", "approved_order_total"),
        ("Open requisitions", "open_requisition_count"),
        ("Pending payment vouchers", "pending_voucher_count"),
    ):
        writer.writerow((label, data[key]))
    writer.writerow(("Overall attendance rate (%)", data["attendance_rate"]))
    for item in data["students_by_level"]:
        writer.writerow((f'Students at level {item["level"] or "Unassigned"}', item["count"]))
    for item in data["course_performance"]:
        writer.writerow(
            (
                f'Course {item["course__code"]} active enrollments',
                item["enrollment_count"],
            )
        )
        writer.writerow(
            (
                f'Course {item["course__code"]} average score',
                item["average_score"] or Decimal("0.00"),
            )
        )
    for resource, count in data["course_resource_counts"].items():
        writer.writerow((f"Course resource: {resource}", count))
    return response


@login_required
def export_institutional_report_pdf(request):
    if not user_can_view_reports(request.user):
        raise PermissionDenied
    semester = _resolve_semester(request)
    site_settings = SiteSettings.get_settings()
    logo_url = (
        request.build_absolute_uri(site_settings.logo.url)
        if site_settings.logo
        else request.build_absolute_uri(static("img/logo.png"))
    )
    html = render_to_string(
        "core/institutional_report_pdf.html",
        {
            **_report_data(semester),
            "site_settings": site_settings,
            "logo_url": logo_url,
        },
    )
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="institutional-report.pdf"'
    result = pisa.CreatePDF(html, dest=response, link_callback=pdf_link_callback)
    if result.err:
        logger.error("PDF generation failed for the institutional report.")
        return HttpResponse(
            "The PDF report could not be generated.",
            status=500,
            content_type="text/plain",
        )
    return response

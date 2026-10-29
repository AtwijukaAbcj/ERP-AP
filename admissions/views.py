import logging
import smtplib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db import IntegrityError
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.utils import log_activity
from .decorators import admissions_permission
from .forms import (
    AdmissionApplicationForm,
    ApplicationStatusForm,
    ApplicationStatusSettingsForm,
    LinkStudentForm,
    ProvisionAcceptedStudentForm,
)
from .models import Application, ApplicationStatus
from .services import provision_accepted_student, transition_application


logger = logging.getLogger(__name__)


@login_required
@admissions_permission("admissions.view_applications")
def dashboard(request):
    counts = dict(
        Application.objects.values_list("status")
        .annotate(total=Count("pk"))
        .values_list("status", "total")
    )
    status_counts = [
        (status.name, counts.get(status.code, 0))
        for status in ApplicationStatus.objects.all()
    ]
    return render(
        request,
        "admissions/dashboard.html",
        {"status_counts": status_counts},
    )


@login_required
@admissions_permission("admissions.view_applications")
def application_list(request):
    applications = Application.objects.select_related("program", "linked_student")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        applications = applications.filter(
            Q(application_number__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if ApplicationStatus.objects.filter(code=status).exists():
        applications = applications.filter(status=status)
    page_obj = Paginator(applications, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "admissions/application_list.html",
        {
            "applications": page_obj,
            "page_obj": page_obj,
            "query": query,
            "selected_status": status,
            "statuses": ApplicationStatus.objects.values_list("code", "name"),
        },
    )


@login_required
@admissions_permission("admissions.manage_applications")
@transaction.atomic
def application_status_settings(request):
    if request.method == "POST":
        form = ApplicationStatusSettingsForm(request.POST)
        if form.is_valid():
            status = form.save()
            log_activity(
                request.user,
                "CREATE",
                f"Admission status {status.name} created.",
                request=request,
                instance=status,
                after={"code": status.code},
            )
            messages.success(request, f"Status “{status.name}” was created.")
            return redirect("admissions:application_status_settings")
    else:
        form = ApplicationStatusSettingsForm()
    statuses = ApplicationStatus.objects.all()
    return render(
        request,
        "admissions/application_status_settings.html",
        {"form": form, "statuses": statuses},
    )


@login_required
@admissions_permission("admissions.manage_applications")
@transaction.atomic
def application_status_edit(request, pk):
    status = get_object_or_404(ApplicationStatus, pk=pk)
    if request.method == "POST":
        form = ApplicationStatusSettingsForm(request.POST, instance=status)
        if form.is_valid():
            before = {"name": status.name}
            form.save()
            log_activity(
                request.user,
                "UPDATE",
                f"Admission status {status.name} updated.",
                request=request,
                instance=status,
                before=before,
                after={"name": status.name},
            )
            messages.success(request, f"Status “{status.name}” was updated.")
            return redirect("admissions:application_status_settings")
    else:
        form = ApplicationStatusSettingsForm(instance=status)
    statuses = ApplicationStatus.objects.all()
    return render(
        request,
        "admissions/application_status_settings.html",
        {"form": form, "statuses": statuses, "editing_status": status},
    )


@login_required
@admissions_permission("admissions.manage_applications")
@require_POST
def application_status_toggle(request, pk):
    status = get_object_or_404(ApplicationStatus, pk=pk)
    was_active = status.is_active
    status.is_active = not status.is_active
    status.save(update_fields=("is_active",))
    action = "activated" if status.is_active else "deactivated"
    log_activity(
        request.user,
        "UPDATE",
        f"Admission status {status.name} {action}.",
        request=request,
        instance=status,
        before={"is_active": was_active},
        after={"is_active": status.is_active},
    )
    messages.success(request, f"Status “{status.name}” was {action}.")
    return redirect("admissions:application_status_settings")


@login_required
@admissions_permission("admissions.manage_applications")
@transaction.atomic
def application_create(request):
    if request.method == "POST":
        form = AdmissionApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.created_by = request.user
            application.save()
            log_activity(
                request.user,
                "CREATE",
                f"Admission application {application.application_number} created.",
                request=request,
                instance=application,
                after={"status": application.status},
            )
            messages.success(
                request,
                f"Application {application.application_number} was created.",
            )
            return redirect("admissions:application_detail", pk=application.pk)
    else:
        form = AdmissionApplicationForm()
    return render(
        request,
        "admissions/application_form.html",
        {"form": form, "title": "New application"},
    )


@login_required
@admissions_permission("admissions.view_applications")
def application_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("program", "linked_student__student"),
        pk=pk,
    )
    return render(
        request,
        "admissions/application_detail.html",
        {
            "application": application,
            "status_form": ApplicationStatusForm(application),
            "student_form": LinkStudentForm(application),
            "provision_form": ProvisionAcceptedStudentForm(),
        },
    )


@login_required
@admissions_permission("admissions.manage_applications")
@transaction.atomic
def application_edit(request, pk):
    application = get_object_or_404(Application, pk=pk)
    if application.status not in {
        Application.Status.DRAFT,
        Application.Status.SUBMITTED,
    }:
        raise PermissionDenied("Applications can only be edited before review.")
    if request.method == "POST":
        form = AdmissionApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            log_activity(
                request.user,
                "UPDATE",
                f"Admission application {application.application_number} updated.",
                request=request,
                instance=application,
            )
            messages.success(request, "Application details were updated.")
            return redirect("admissions:application_detail", pk=application.pk)
    else:
        form = AdmissionApplicationForm(instance=application)
    return render(
        request,
        "admissions/application_form.html",
        {"form": form, "title": f"Edit {application.application_number}"},
    )


@login_required
@admissions_permission("admissions.review_applications")
@require_POST
def application_change_status(request, pk):
    application = get_object_or_404(Application, pk=pk)
    form = ApplicationStatusForm(application, request.POST)
    if form.is_valid():
        if form.cleaned_data["status"] == application.status:
            messages.info(request, "The application is already in that status.")
            return redirect("admissions:application_detail", pk=application.pk)
        try:
            application = transition_application(
                application.pk,
                form.cleaned_data["status"],
                request.user,
                form.cleaned_data["comment"],
                request=request,
            )
        except ValidationError as error:
            form.add_error("status", error)
        else:
            messages.success(
                request,
                f"Application status changed to {application.get_status_display()}.",
            )
            return redirect("admissions:application_detail", pk=application.pk)
    return render(
        request,
        "admissions/application_detail.html",
        {
            "application": application,
            "status_form": form,
            "student_form": LinkStudentForm(application),
            "provision_form": ProvisionAcceptedStudentForm(),
        },
        status=400,
    )


@login_required
@admissions_permission("admissions.link_students")
@require_POST
@transaction.atomic
def application_link_student(request, pk):
    application = get_object_or_404(
        Application.objects.select_for_update(),
        pk=pk,
    )
    if application.status != Application.Status.ACCEPTED:
        raise PermissionDenied("Only accepted applicants can be linked to students.")
    form = LinkStudentForm(application, request.POST)
    if form.is_valid():
        student = form.cleaned_data["student"]
        if application.program_id and student.program_id != application.program_id:
            form.add_error("student", "The student's program does not match this application.")
        else:
            with transaction.atomic():
                application.linked_student = student
                application.save(update_fields=("linked_student", "updated_at"))
                log_activity(
                    request.user,
                    "UPDATE",
                    f"Admission application {application.application_number} linked to "
                    f"student record {student.registration_number or student.pk}.",
                    request=request,
                    instance=application,
                    after={"linked_student_id": student.pk},
                )
            messages.success(request, "The admitted applicant was linked to the student record.")
            return redirect("admissions:application_detail", pk=application.pk)
    return render(
        request,
        "admissions/application_detail.html",
        {
            "application": application,
            "status_form": ApplicationStatusForm(application),
            "student_form": form,
            "provision_form": ProvisionAcceptedStudentForm(),
        },
        status=400,
    )


@login_required
@admissions_permission("admissions.link_students")
@require_POST
def application_provision_student(request, pk):
    application = get_object_or_404(Application, pk=pk)
    if application.status != Application.Status.ACCEPTED:
        raise PermissionDenied("Only accepted applicants can be registered as students.")

    form = ProvisionAcceptedStudentForm(request.POST)
    if form.is_valid():
        try:
            user, student = provision_accepted_student(
                application.pk,
                registration_number=form.cleaned_data["registration_number"],
                level=form.cleaned_data["level"],
                year=form.cleaned_data["year"],
                actor=request.user,
                request=request,
            )
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(
                None,
                "The student account or registration number already exists. Review the records and try again.",
            )
        else:
            reset_form = PasswordResetForm({"email": user.email})
            if reset_form.is_valid():
                try:
                    reset_form.save(
                        request=request,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        use_https=request.is_secure(),
                    )
                except (OSError, smtplib.SMTPException):
                    logger.exception(
                        "Could not send password reset email for provisioned student %s.",
                        student.pk,
                    )
                    messages.warning(
                        request,
                        "The student record was created, but the password setup email could not be sent. "
                        "Check email configuration and resend the password reset.",
                    )
                else:
                    messages.success(
                        request,
                        "The accepted applicant was registered as a student and a password setup email was sent.",
                    )
            else:
                logger.error(
                    "Password setup email could not be prepared for provisioned student %s.",
                    student.pk,
                )
                messages.warning(
                    request,
                    "The student record was created, but the password setup email could not be prepared.",
                )
            return redirect("admissions:application_detail", pk=application.pk)

    return render(
        request,
        "admissions/application_detail.html",
        {
            "application": application,
            "status_form": ApplicationStatusForm(application),
            "student_form": LinkStudentForm(application),
            "provision_form": form,
        },
        status=400,
    )

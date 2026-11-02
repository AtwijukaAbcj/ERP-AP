from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Student
from audit.utils import log_activity

from .decorators import clinical_permission
from .forms import ClinicalLogEntryForm, ClinicalPlacementForm, WardForm
from .models import ClinicalLogEntry, ClinicalPlacement, Ward
from .services import review_log_entry, transition_placement


def _can_manage_clinical(user):
    return _has_clinical_permission(user, "clinical.manage_placements")


def _has_clinical_permission(user, permission_code):
    if user.has_permission(permission_code):
        return True
    return bool(
        not user.permission_overrides.filter(
            permission__code=permission_code,
            effect="deny",
        ).exists()
        and user.has_permission("clinical")
    )


@login_required
def placement_list(request):
    manager_access = _can_manage_clinical(request.user)
    staff_access = (
        manager_access
        or _has_clinical_permission(request.user, "clinical.view_placements")
        or _has_clinical_permission(request.user, "clinical.verify_log_entries")
    )
    if not staff_access and not request.user.is_student:
        raise PermissionDenied

    placements = ClinicalPlacement.objects.select_related(
        "student__student",
        "student__program",
        "ward",
        "semester__session",
        "supervisor",
    ).prefetch_related("log_entries").annotate(
        verified_hours=Sum(
            "log_entries__hours",
            filter=Q(log_entries__status=ClinicalLogEntry.Status.VERIFIED),
        )
    )
    if not staff_access:
        student = get_object_or_404(Student, student=request.user)
        placements = placements.filter(student=student)

    return render(
        request,
        "clinical/placement_list.html",
        {
            "placements": placements,
            "can_manage": manager_access,
            "can_review": _has_clinical_permission(
                request.user,
                "clinical.verify_log_entries",
            ),
            "show_students": staff_access,
            "title": "Clinical placements",
        },
    )


@login_required
@clinical_permission("clinical.manage_placements")
def ward_list(request):
    ward_id = request.POST.get("edit") if request.method == "POST" else request.GET.get("edit")
    ward_instance = get_object_or_404(Ward, pk=ward_id) if ward_id else None
    form = WardForm(request.POST or None, instance=ward_instance)
    if request.method == "POST" and form.is_valid():
        ward = form.save()
        action = "UPDATE" if ward_instance else "CREATE"
        log_activity(
            request.user,
            action,
            f"Clinical ward {ward.name} at {ward.facility} saved.",
            request=request,
            instance=ward,
            after={"capacity": ward.capacity, "is_active": ward.is_active},
        )
        messages.success(request, "Clinical ward saved.")
        return redirect("clinical:ward_list")
    return render(
        request,
        "clinical/ward_list.html",
        {
            "wards": Ward.objects.all(),
            "form": form,
            "ward_instance": ward_instance,
            "title": "Clinical wards",
        },
    )


@login_required
@clinical_permission("clinical.manage_placements")
@transaction.atomic
def placement_create(request):
    form = ClinicalPlacementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ward = Ward.objects.select_for_update().get(pk=form.cleaned_data["ward"].pk)
        Student.objects.select_for_update().get(pk=form.cleaned_data["student"].pk)
        form.instance.ward = ward
        form.instance.created_by = request.user
        for field, error in form.validate_conflicts().items():
            form.add_error(field, error)
        if not form.errors:
            try:
                form.instance.full_clean()
                placement = form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                log_activity(
                    request.user,
                    "CREATE",
                    f"Clinical placement created for {placement.student} at {placement.ward}.",
                    request=request,
                    instance=placement,
                    after={
                        "student_id": placement.student_id,
                        "ward_id": placement.ward_id,
                        "semester_id": placement.semester_id,
                        "starts_on": placement.starts_on.isoformat(),
                        "ends_on": placement.ends_on.isoformat(),
                    },
                )
                messages.success(request, "Clinical placement created.")
                return redirect("clinical:placement_list")
    return render(
        request,
        "clinical/placement_form.html",
        {"form": form, "title": "Assign clinical placement"},
    )


@login_required
@require_POST
@clinical_permission("clinical.manage_placements")
def placement_change_status(request, pk):
    status = request.POST.get("status", "")
    reason = request.POST.get("reason", "").strip()
    get_object_or_404(ClinicalPlacement, pk=pk)
    if status not in ClinicalPlacement.Status.values:
        messages.error(request, "Choose a valid placement status.")
        return redirect("clinical:placement_list")
    try:
        placement = transition_placement(
            pk,
            status,
            request.user,
            reason,
            request=request,
        )
    except ValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"Placement status updated to {placement.get_status_display()}.",
        )
    return redirect("clinical:placement_list")


@login_required
def placement_detail(request, pk):
    placement = get_object_or_404(
        ClinicalPlacement.objects.select_related(
            "student__student",
            "ward",
            "semester__session",
            "supervisor",
        ).prefetch_related("log_entries__reviewed_by"),
        pk=pk,
    )
    own_placement = (
        request.user.is_active
        and request.user.is_student
        and placement.student.student_id == request.user.pk
        and placement.student.status == Student.Status.ACTIVE
    )
    can_manage = _can_manage_clinical(request.user)
    can_view = request.user.has_permission("clinical.view_placements")
    can_review = request.user.has_permission("clinical.verify_log_entries")
    if not (own_placement or can_view or can_manage or can_review):
        raise PermissionDenied

    form = None
    if own_placement and placement.status == ClinicalPlacement.Status.IN_PROGRESS:
        form = ClinicalLogEntryForm(
            request.POST or None,
            placement=placement,
        )
        if request.method == "POST" and form.is_valid():
            entry = form.save(commit=False)
            entry.placement = placement
            entry.save()
            log_activity(
                request.user,
                "CREATE",
                f"Clinical log entry submitted for placement {placement.pk}.",
                request=request,
                instance=entry,
                after={"date": entry.date.isoformat(), "hours": str(entry.hours)},
            )
            messages.success(request, "Clinical activity log submitted for review.")
            return redirect("clinical:placement_detail", pk=placement.pk)
    return render(
        request,
        "clinical/placement_detail.html",
        {
            "placement": placement,
            "form": form,
            "can_manage": can_manage,
            "can_review": can_review,
            "verified_hours": placement.log_entries.filter(
                status=ClinicalLogEntry.Status.VERIFIED
            ).aggregate(total=Sum("hours"))["total"]
            or 0,
            "title": "Clinical placement details",
        },
        status=400 if request.method == "POST" and form is not None else 200,
    )


@login_required
@require_POST
@clinical_permission("clinical.verify_log_entries")
def log_entry_review(request, pk):
    entry = get_object_or_404(
        ClinicalLogEntry.objects.select_related("placement__supervisor"),
        pk=pk,
    )
    if entry.placement.supervisor_id != request.user.pk and not request.user.is_superuser:
        raise PermissionDenied
    status = request.POST.get("status", "")
    feedback = request.POST.get("supervisor_feedback", "")
    try:
        review_log_entry(pk, status, request.user, feedback, request=request)
    except ValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Clinical log entry reviewed.")
    return redirect("clinical:placement_detail", pk=entry.placement_id)

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.utils import log_activity

from .models import ClinicalLogEntry, ClinicalPlacement, PlacementStatusHistory


PLACEMENT_TRANSITIONS = {
    ClinicalPlacement.Status.PLANNED: {
        ClinicalPlacement.Status.IN_PROGRESS,
        ClinicalPlacement.Status.CANCELLED,
    },
    ClinicalPlacement.Status.IN_PROGRESS: {
        ClinicalPlacement.Status.COMPLETED,
        ClinicalPlacement.Status.CANCELLED,
    },
    ClinicalPlacement.Status.COMPLETED: set(),
    ClinicalPlacement.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_placement(placement_id, to_status, actor, reason="", request=None):
    placement = ClinicalPlacement.objects.select_for_update().get(pk=placement_id)
    if to_status not in ClinicalPlacement.Status.values:
        raise ValidationError(f"'{to_status}' is not a valid placement status.")
    if to_status not in PLACEMENT_TRANSITIONS.get(placement.status, set()):
        raise ValidationError(
            f"A placement cannot move from {placement.get_status_display()} to "
            f"{ClinicalPlacement.Status(to_status).label}."
        )
    previous_status = placement.status
    placement.status = to_status
    placement.save(update_fields=("status", "updated_at"))
    PlacementStatusHistory.objects.create(
        placement=placement,
        from_status=previous_status,
        to_status=to_status,
        reason=reason,
        changed_by=actor,
    )
    log_activity(
        actor,
        "UPDATE",
        f"Clinical placement {placement.pk} changed from {previous_status} "
        f"to {to_status}.",
        request=request,
        instance=placement,
        before={"status": previous_status},
        after={"status": to_status},
    )
    return placement


@transaction.atomic
def review_log_entry(entry_id, status, actor, feedback="", request=None):
    entry = ClinicalLogEntry.objects.select_for_update().select_related(
        "placement__student"
    ).get(pk=entry_id)
    if entry.status != ClinicalLogEntry.Status.PENDING:
        raise ValidationError("Only pending clinical log entries can be reviewed.")
    if status not in {
        ClinicalLogEntry.Status.VERIFIED,
        ClinicalLogEntry.Status.RETURNED,
    }:
        raise ValidationError("Choose a valid clinical log review outcome.")
    if status == ClinicalLogEntry.Status.RETURNED and not feedback.strip():
        raise ValidationError("Feedback is required when returning a log entry.")

    entry.status = status
    entry.supervisor_feedback = feedback.strip()
    entry.reviewed_by = actor
    entry.reviewed_at = timezone.now()
    entry.save(
        update_fields=(
            "status",
            "supervisor_feedback",
            "reviewed_by",
            "reviewed_at",
        )
    )
    log_activity(
        actor,
        "UPDATE",
        f"Clinical log entry {entry.pk} was {status}.",
        request=request,
        instance=entry,
        after={"status": status, "placement_id": entry.placement_id},
    )
    return entry

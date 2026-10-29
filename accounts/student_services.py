from django.core.exceptions import ValidationError
from django.db import transaction

from audit.utils import log_activity
from .models import Student, StudentStatusHistory


STATUS_TRANSITIONS = {
    Student.Status.ACTIVE: {
        Student.Status.ON_LEAVE,
        Student.Status.SUSPENDED,
        Student.Status.GRADUATED,
        Student.Status.WITHDRAWN,
    },
    Student.Status.ON_LEAVE: {
        Student.Status.ACTIVE,
        Student.Status.SUSPENDED,
        Student.Status.WITHDRAWN,
    },
    Student.Status.SUSPENDED: {
        Student.Status.ACTIVE,
        Student.Status.ON_LEAVE,
        Student.Status.WITHDRAWN,
    },
    Student.Status.GRADUATED: set(),
    Student.Status.WITHDRAWN: set(),
}


@transaction.atomic
def transition_student_status(student_id, to_status, actor, reason="", request=None):
    student = Student.objects.select_for_update().get(pk=student_id)
    if to_status not in Student.Status.values:
        raise ValidationError(f"'{to_status}' is not a valid student status.")
    if to_status not in STATUS_TRANSITIONS[student.status]:
        raise ValidationError(
            f"A student cannot move from {student.get_status_display()} "
            f"to {Student.Status(to_status).label}."
        )

    previous_status = student.status
    student.status = to_status
    student.save(update_fields=("status",))
    StudentStatusHistory.objects.create(
        student=student,
        from_status=previous_status,
        to_status=to_status,
        reason=reason,
        changed_by=actor,
    )
    log_activity(
        actor,
        "UPDATE",
        f"Student {student.registration_number or student.pk} status changed "
        f"from {previous_status} to {to_status}.",
        request=request,
        instance=student,
        before={"status": previous_status},
        after={"status": to_status},
    )
    return student

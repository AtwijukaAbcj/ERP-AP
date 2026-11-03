import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Student, User
from audit.utils import log_activity
from .models import (
    Application,
    ApplicationStatus,
    ApplicationStatusHistory,
)


@transaction.atomic
def transition_application(application_id, to_status, actor, comment="", request=None):
    application = Application.objects.select_for_update().get(pk=application_id)
    target_status = ApplicationStatus.objects.filter(
        code=to_status,
        is_active=True,
    ).first()
    if target_status is None:
        raise ValidationError(f"'{to_status}' is not a valid application status.")

    previous_status = application.status
    if previous_status == to_status:
        return application
    application.status = to_status
    if comment:
        application.decision_notes = comment
    application.save(update_fields=("status", "decision_notes", "updated_at"))
    ApplicationStatusHistory.objects.create(
        application=application,
        from_status=previous_status,
        to_status=to_status,
        comment=comment,
        changed_by=actor,
    )
    log_activity(
        actor,
        "UPDATE",
        f"Application {application.application_number} changed from "
        f"{previous_status} to {to_status}.",
        request=request,
        instance=application,
        before={"status": previous_status},
        after={"status": to_status},
    )
    return application


@transaction.atomic
def provision_accepted_student(
    application_id,
    *,
    year,
    semester,
    actor,
    request=None,
):
    application = Application.objects.select_for_update().get(pk=application_id)
    if application.status != Application.Status.ACCEPTED:
        raise ValidationError("Only accepted applicants can be registered as students.")
    if application.linked_student_id:
        raise ValidationError("This application is already linked to a student record.")
    if not application.program_id:
        raise ValidationError("Assign a programme before registering this student.")
    if not application.program.level_id:
        raise ValidationError(
            "Assign an academic level to the programme before registering this student."
        )
    if User.objects.filter(email__iexact=application.email).exists():
        raise ValidationError(
            "An account already uses this email. Link its student record instead."
        )

    username_base = slugify(application.email.partition("@")[0]) or "student"
    username = username_base[:150]
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix_text = f"-{suffix}"
        username = f"{username_base[:150 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    user = User.objects.create_user(
        username=username,
        email=application.email,
        password=secrets.token_urlsafe(48),
        first_name=application.first_name,
        last_name=application.last_name,
        is_student=True,
    )
    student = Student.objects.create(
        student=user,
        program=application.program,
        level=application.program.level.name,
        year=year,
        semester=semester,
        date_of_birth=application.date_of_birth,
        cohort=f"{application.intake} {application.academic_year}",
        admission_date=timezone.localdate(),
        next_of_kin_name=application.next_of_kin_name,
        next_of_kin_phone=application.next_of_kin_phone,
    )
    application.linked_student = student
    application.save(update_fields=("linked_student", "updated_at"))
    log_activity(
        actor,
        "CREATE",
        f"Accepted application {application.application_number} provisioned as "
        f"student {student.registration_number}.",
        request=request,
        instance=student,
        after={
            "application_id": application.pk,
            "student_id": student.pk,
            "registration_number": student.registration_number,
        },
    )
    return user, student

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

ACCOUNT_CATEGORIES = (
    ("is_student", _("Students")),
    ("is_lecturer", _("Lecturers")),
    ("is_parent", _("Parents")),
    ("is_registrar", _("Registrars")),
    ("is_faculty_admin", _("Faculty administrators")),
    ("is_dep_head", _("Department heads")),
    ("is_finance", _("Finance users")),
    ("is_finance_manager", _("Finance managers")),
    ("is_accountant", _("Accountants")),
    ("is_procurement_officer", _("Procurement officers")),
    ("is_procurement_manager", _("Procurement managers")),
    ("is_internal_auditor", _("Internal auditors")),
    ("is_principal", _("Principals")),
    ("is_superuser", _("Super administrators")),
)

STAFF_FLAGS = (
    "is_lecturer",
    "is_registrar",
    "is_faculty_admin",
    "is_dep_head",
    "is_finance",
    "is_finance_manager",
    "is_accountant",
    "is_procurement_officer",
    "is_procurement_manager",
    "is_internal_auditor",
    "is_principal",
)


def can_send_group_messages(user):
    return bool(
        user.is_authenticated
        and user.is_active
        and (
            user.is_staff
            or user.is_superuser
            or any(getattr(user, flag, False) for flag in STAFF_FLAGS)
        )
    )


def resolve_recipients(sender, recipient_type, users=None, roles=None, categories=None):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    recipients = User.objects.filter(is_active=True)
    if recipient_type == "individual":
        recipients = recipients.filter(pk__in=[user.pk for user in users or ()])
    elif recipient_type == "role":
        recipients = recipients.filter(
            Q(role__in=roles or ()) | Q(roles__in=roles or ())
        )
    elif recipient_type == "category":
        category_fields = set(categories or ())
        category_query = Q()
        for field, _label in ACCOUNT_CATEGORIES:
            if field in category_fields:
                category_query |= Q(**{field: True})
        if not category_query:
            return User.objects.none()
        recipients = recipients.filter(category_query)
    else:
        return User.objects.none()
    return recipients.exclude(pk=sender.pk).distinct().order_by("last_name", "first_name", "username")

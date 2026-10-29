from audit.models import ActivityLog

def log_activity(
    user,
    action,
    description="",
    *,
    request=None,
    instance=None,
    before=None,
    after=None,
):
    authenticated_user = user if getattr(user, "is_authenticated", False) else None
    ip_address = None
    user_agent = ""

    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

    target_model = ""
    object_id = ""
    if instance is not None:
        target_model = instance._meta.label
        if instance.pk is not None:
            object_id = str(instance.pk)

    return ActivityLog.objects.create(
        user=authenticated_user,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        target_model=target_model,
        object_id=object_id,
        before=before,
        after=after,
    )

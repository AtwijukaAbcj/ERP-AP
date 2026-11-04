from .models import MessageDelivery, UserNotification


def unread_message_count(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "unread_message_count": 0,
            "unread_notification_count": 0,
        }
    return {
        "unread_message_count": MessageDelivery.objects.filter(
            recipient=user,
            read_at__isnull=True,
        ).count(),
        "unread_notification_count": UserNotification.objects.filter(
            recipient=user,
            read_at__isnull=True,
        ).count(),
    }

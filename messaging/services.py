from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.text import Truncator

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageDelivery,
    UserNotification,
)


@transaction.atomic
def start_conversation(sender, recipients, subject, body, is_group):
    recipient_ids = {recipient.pk for recipient in recipients if recipient.pk != sender.pk}
    if not recipient_ids:
        raise ValueError("A conversation must have at least one recipient.")

    conversation = None
    if not is_group and len(recipient_ids) == 1:
        recipient_id = next(iter(recipient_ids))
        conversation = (
            Conversation.objects.filter(is_group=False)
            .filter(participants=sender)
            .filter(participants__pk=recipient_id)
            .annotate(participant_count=Count("participants", distinct=True))
            .filter(participant_count=2)
            .order_by("-updated_at")
            .first()
        )

    if conversation is None:
        conversation = Conversation.objects.create(
            subject=subject,
            created_by=sender,
            is_group=is_group,
        )
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, user_id=user_id)
                for user_id in {sender.pk, *recipient_ids}
            ]
        )
    elif not conversation.subject and subject:
        conversation.subject = subject
        conversation.save(update_fields=("subject",))

    post_message(conversation, sender, body)
    return conversation


@transaction.atomic
def post_message(conversation, sender, body):
    if not conversation.participants.filter(pk=sender.pk).exists():
        raise PermissionDenied("You are not a participant in this conversation.")

    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=body,
    )
    recipient_ids = (
        conversation.participants.filter(is_active=True)
        .exclude(pk=sender.pk)
        .values_list("pk", flat=True)
    )
    recipient_ids = list(recipient_ids)
    MessageDelivery.objects.bulk_create(
        [
            MessageDelivery(message=message, recipient_id=recipient_id)
            for recipient_id in recipient_ids
        ]
    )
    notification_title = conversation.subject or f"New message from {sender.get_full_name}"
    notification_body = Truncator(body).chars(180)
    UserNotification.objects.bulk_create(
        [
            UserNotification(
                recipient_id=recipient_id,
                actor=sender,
                conversation=conversation,
                title=notification_title,
                body=notification_body,
            )
            for recipient_id in recipient_ids
        ]
    )
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=("updated_at",))
    return message

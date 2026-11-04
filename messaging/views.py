from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .forms import ComposeMessageForm
from .models import Conversation, MessageDelivery, UserNotification
from .recipients import can_send_group_messages
from .services import post_message, start_conversation


@login_required
def inbox(request):
    conversations = (
        Conversation.objects.filter(participants=request.user)
        .annotate(
            unread_count=Count(
                "messages__deliveries",
                filter=Q(
                    messages__deliveries__recipient=request.user,
                    messages__deliveries__read_at__isnull=True,
                ),
            )
        )
        .prefetch_related("participants")
        .order_by("-updated_at")
    )
    return render(
        request,
        "messaging/inbox.html",
        {
            "conversations": conversations,
            "can_send_group_messages": can_send_group_messages(request.user),
        },
    )


@login_required
def notification_list(request):
    notifications = UserNotification.objects.filter(
        recipient=request.user
    ).select_related("actor", "conversation")[:100]
    return render(
        request,
        "messaging/notifications.html",
        {"notifications": notifications},
    )


@login_required
def open_notification(request, pk):
    notification = get_object_or_404(
        UserNotification,
        pk=pk,
        recipient=request.user,
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at",))
    if notification.conversation_id:
        return redirect("messaging:conversation", pk=notification.conversation_id)
    if notification.target_url and url_has_allowed_host_and_scheme(
        notification.target_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(notification.target_url)
    return redirect("messaging:notifications")


@login_required
@require_http_methods(["POST"])
def mark_notifications_read(request):
    UserNotification.objects.filter(
        recipient=request.user,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    messages.success(request, "All notifications have been marked as read.")
    return redirect("messaging:notifications")


@login_required
@require_http_methods(["GET", "POST"])
def compose(request):
    form = ComposeMessageForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        recipients = list(form.get_recipients())
        is_group = (
            form.cleaned_data["recipient_type"] != "individual"
            or len(recipients) > 1
        )
        conversation = start_conversation(
            request.user,
            recipients,
            form.cleaned_data["subject"].strip(),
            form.cleaned_data["body"].strip(),
            is_group,
        )
        messages.success(request, "Your message has been sent.")
        return redirect("messaging:conversation", pk=conversation.pk)
    return render(
        request,
        "messaging/compose.html",
        {
            "form": form,
            "can_send_group_messages": can_send_group_messages(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.filter(participants=request.user).prefetch_related(
            "participants",
            "messages__sender",
        ),
        pk=pk,
    )
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if not body:
            messages.error(request, "Enter a message before sending.")
        elif len(body) > 10000:
            messages.error(request, "Messages must be 10,000 characters or fewer.")
        else:
            post_message(conversation, request.user, body)
            return redirect("messaging:conversation", pk=conversation.pk)
    else:
        MessageDelivery.objects.filter(
            recipient=request.user,
            message__conversation=conversation,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
    return render(
        request,
        "messaging/conversation.html",
        {
            "conversation": conversation,
            "messages_list": conversation.messages.select_related("sender"),
        },
    )

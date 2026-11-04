from django.contrib import admin

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageDelivery,
    UserNotification,
)


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "created_by", "is_group", "updated_at")
    list_filter = ("is_group",)
    search_fields = ("subject", "messages__body")
    inlines = (ConversationParticipantInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "sent_at")
    search_fields = ("body", "sender__username", "conversation__subject")


@admin.register(MessageDelivery)
class MessageDeliveryAdmin(admin.ModelAdmin):
    list_display = ("message", "recipient", "read_at")
    list_filter = ("read_at",)
    search_fields = ("recipient__username", "message__body")


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "actor", "created_at", "read_at")
    list_filter = ("read_at", "created_at")
    search_fields = ("title", "body", "recipient__username", "actor__username")

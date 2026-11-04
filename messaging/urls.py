from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("notifications/", views.notification_list, name="notifications"),
    path(
        "notifications/<int:pk>/",
        views.open_notification,
        name="open_notification",
    ),
    path(
        "notifications/read-all/",
        views.mark_notifications_read,
        name="mark_notifications_read",
    ),
    path("compose/", views.compose, name="compose"),
    path("<int:pk>/", views.conversation_detail, name="conversation"),
]

from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("applications/", views.application_list, name="application_list"),
    path("statuses/", views.application_status_settings, name="application_status_settings"),
    path(
        "statuses/<int:pk>/edit/",
        views.application_status_edit,
        name="application_status_edit",
    ),
    path(
        "statuses/<int:pk>/toggle/",
        views.application_status_toggle,
        name="application_status_toggle",
    ),
    path("applications/new/", views.application_create, name="application_create"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
    path(
        "applications/<int:pk>/status/",
        views.application_change_status,
        name="application_change_status",
    ),
    path(
        "applications/<int:pk>/link-student/",
        views.application_link_student,
        name="application_link_student",
    ),
    path(
        "applications/<int:pk>/register-student/",
        views.application_provision_student,
        name="application_provision_student",
    ),
]

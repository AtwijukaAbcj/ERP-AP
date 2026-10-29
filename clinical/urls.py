from django.urls import path

from . import views

app_name = "clinical"

urlpatterns = [
    path("placements/", views.placement_list, name="placement_list"),
    path("placements/new/", views.placement_create, name="placement_create"),
    path(
        "placements/<int:pk>/",
        views.placement_detail,
        name="placement_detail",
    ),
    path(
        "placements/<int:pk>/status/",
        views.placement_change_status,
        name="placement_change_status",
    ),
    path("wards/", views.ward_list, name="ward_list"),
    path("log-entries/<int:pk>/review/", views.log_entry_review, name="log_entry_review"),
]

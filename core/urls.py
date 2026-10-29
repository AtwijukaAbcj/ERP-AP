from django.urls import path

from .views import (
    home_view,
    post_add,
    edit_post,
    delete_post,
    session_list_view,
    session_add_view,
    session_update_view,
    session_delete_view,
    semester_list_view,
    semester_add_view,
    semester_update_view,
    semester_delete_view,
    dashboard_view,
    site_settings_view,
    course_enrollment_view,
)
from . import views
from .views import room_list, add_room
from .reporting import (
    institutional_reports,
    export_institutional_report_csv,
    export_institutional_report_pdf,
)

urlpatterns = [
    path("", views.home_view, name="home"),
    path("add_item/", views.post_add, name="add_item"),
    path("item/<int:pk>/edit/", views.edit_post, name="edit_post"),
    path("item/<int:pk>/delete/", views.delete_post, name="delete_post"),
    path("session/", views.session_list_view, name="session_list"),
    path("session/add/", views.session_add_view, name="add_session"),
    path("session/<int:pk>/edit/", views.session_update_view, name="edit_session"),
    path("session/<int:pk>/delete/", views.session_delete_view, name="delete_session"),
    path("semester/", views.semester_list_view, name="semester_list"),
    path("semester/add/", views.semester_add_view, name="add_semester"),
    path("semester/<int:pk>/edit/", views.semester_update_view, name="edit_semester"),
    path("semester/<int:pk>/delete/", views.semester_delete_view, name="delete_semester"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("reports/", institutional_reports, name="institutional_reports"),
    path(
        "reports/export/csv/",
        export_institutional_report_csv,
        name="export_institutional_report_csv",
    ),
    path(
        "reports/export/pdf/",
        export_institutional_report_pdf,
        name="export_institutional_report_pdf",
    ),
    path("course-enrollment/", course_enrollment_view, name="course_enrollment"),
    
    # Timetable URLs
    path('timetables/', views.timetable_list, name='timetable_list'),
    path('timetables/add/', views.add_timetable, name='add_timetable'),
    path('timetables/<int:pk>/', views.timetable_detail, name='timetable_detail'),
    path('timetables/<int:timetable_id>/add-entry/', views.add_timetable_entry, name='add_timetable_entry'),
    path('rooms/', room_list, name='room_list'),
    path('rooms/add/', add_room, name='add_room'),
    path('timetables/<int:pk>/edit/', views.edit_timetable, name='edit_timetable'),
    path('timetables/<int:pk>/delete/', views.delete_timetable, name='delete_timetable'),
    path("my-timetable/", views.student_timetable_view, name="student_timetable"),
    path('timetables/entry/<int:pk>/delete/', views.delete_timetable_entry, name='delete_timetable_entry'),
    path("settings/", views.site_settings_view, name="site_settings"),
]

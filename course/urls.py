from django.urls import path
from . import views
from .views import add_faculty_view
from .views import manage_faculties_view
from .views import export_faculties_pdf
urlpatterns = [
    # Program urls
    path("", views.ProgramFilterView.as_view(), name="programs"),
    path("<int:pk>/detail/", views.program_detail, name="program_detail"),
    path("add/", views.program_add, name="add_program"),
    path("levels/", views.program_level_list, name="program_level_list"),
    path(
        "levels/<int:pk>/edit/",
        views.program_level_edit,
        name="program_level_edit",
    ),
    path(
        "levels/<int:pk>/delete/",
        views.program_level_delete,
        name="program_level_delete",
    ),
    path("years/", views.academic_year_list, name="academic_year_list"),
    path(
        "years/<int:pk>/edit/",
        views.academic_year_edit,
        name="academic_year_edit",
    ),
    path(
        "years/<int:pk>/delete/",
        views.academic_year_delete,
        name="academic_year_delete",
    ),
    path("<int:pk>/edit/", views.program_edit, name="edit_program"),
    path("<int:pk>/delete/", views.program_delete, name="program_delete"),
    # Course urls
    path("course/<slug>/detail/", views.course_single, name="course_detail"),
    path("<int:pk>/course/add/", views.course_add, name="course_add"),
    path("course/<slug>/edit/", views.course_edit, name="edit_course"),
    path("course/delete/<slug>/", views.course_delete, name="delete_course"),
    path("faculties/export/pdf/", export_faculties_pdf, name="export_faculties_pdf"),
    # CourseAllocation urls
    path(
        "course/assign/",
        views.CourseAllocationFormView.as_view(),
        name="course_allocation",
    ),
    
    path(
        "course/allocated/",
        views.CourseAllocationFilterView.as_view(),
        name="course_allocation_view",
    ),
    path(
        "allocated_course/<int:pk>/edit/",
        views.edit_allocated_course,
        name="edit_allocated_course",
    ),
    path(
        "course/<int:pk>/deallocate/", views.deallocate_course, name="course_deallocate"
    ),
    # File uploads urls
    path(
        "course/<slug>/documentations/upload/",
        views.handle_file_upload,
        name="upload_file_view",
    ),
    path(
        "course/<slug>/documentations/<int:file_id>/edit/",
        views.handle_file_edit,
        name="upload_file_edit",
    ),
    path(
        "course/<slug>/documentations/<int:file_id>/delete/",
        views.handle_file_delete,
        name="upload_file_delete",
    ),
    # Video uploads urls
    path(
        "course/<slug>/video_tutorials/upload/",
        views.handle_video_upload,
        name="upload_video",
    ),
    path(
        "course/<slug>/video_tutorials/<video_slug>/detail/",
        views.handle_video_single,
        name="video_single",
    ),
    path(
        "course/<slug>/video_tutorials/<video_slug>/edit/",
        views.handle_video_edit,
        name="upload_video_edit",
    ),
    path(
        "course/<slug>/video_tutorials/<video_slug>/delete/",
        views.handle_video_delete,
        name="upload_video_delete",
    ),
    # course registration
    path("course/registration/", views.course_registration, name="course_registration"),
    path("course/drop/", views.course_drop, name="course_drop"),
    path("my_courses/", views.user_course_list, name="user_course_list"),
    path('faculty/add/', add_faculty_view, name='add_faculty'),
    path('faculties/', manage_faculties_view, name='manage_faculties'),
    path('faculties/export/pdf/', export_faculties_pdf, name='export_faculties_pdf'),
    path('faculty/<int:id>/edit/', views.edit_faculty, name='edit_faculty'),
    path('faculty/<int:id>/delete/', views.delete_faculty, name='delete_faculty'),
    path("course/registration/form/", views.course_registration_form_view, name="course_registration_form"),
    

]

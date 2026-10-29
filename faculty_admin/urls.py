from django.urls import path
from . import views
from .views import FacultyLecturerAddView

urlpatterns = [
    # PROGRAM MANAGEMENT
    path("programs/", views.FacultyProgramListView.as_view(), name="faculty_program_list"),
    path("programs/add/", views.FacultyProgramCreateView.as_view(), name="faculty_add_program"),
    path("programs/<int:pk>/", views.FacultyProgramDetailView.as_view(), name="faculty_program_detail"),
    path("programs/<int:pk>/edit/", views.FacultyProgramEditView.as_view(), name="faculty_edit_program"),
    path("programs/<int:pk>/delete/", views.FacultyProgramDeleteView.as_view(), name="faculty_delete_program"),

    # COURSE MANAGEMENT
    path("programs/<int:pk>/add-course/", views.FacultyCourseAddView.as_view(), name="faculty_add_course"),
    path("courses/<slug:slug>/edit/", views.FacultyCourseEditView.as_view(), name="faculty_edit_course"),
    path("courses/", views.FacultyCourseListView.as_view(), name="faculty_course_list"),
    path("courses/<slug:slug>/delete/", views.FacultyCourseDeleteView.as_view(), name="faculty_delete_course"),

    # COURSE ALLOCATION
    path("course-allocation/", views.CourseAllocationListView.as_view(), name="faculty_course_allocation_view"),
    path("course-allocation/add/", views.CourseAllocationCreateView.as_view(), name="faculty_course_allocation"),
    path("course-allocation/<int:pk>/edit/", views.CourseAllocationEditView.as_view(), name="faculty_edit_allocated_course"),
    path("course-allocation/<int:pk>/delete/", views.CourseAllocationDeleteView.as_view(), name="faculty_course_deallocate"),

    # LECTURERS
    path("lecturers/", views.FacultyLecturerListView.as_view(), name="faculty_lecturer_list"),
    path("lecturers/add/", views.FacultyLecturerAddView.as_view(), name="faculty_add_lecturer"),

    # STUDENTS
    path("students/", views.FacultyStudentListView.as_view(), name="faculty_student_list"),
    path("students-by-program/", views.FacultyStudentByProgramView.as_view(), name="faculty_students_by_program"),

    # DASHBOARD COURSES
    path("my-courses/", views.FacultyUserCourseListView.as_view(), name="faculty_user_course_list"),
    path("lecturers/add/", FacultyLecturerAddView.as_view(), name="faculty_add_lecturer"),
    path("lecturers/<int:pk>/edit/", views.FacultyLecturerEditView.as_view(), name="faculty_edit_lecturer"),
    path('lecturers/export/pdf/', views.FacultyLecturerListPDFView.as_view(), name='faculty_lecturer_list_pdf'),

]

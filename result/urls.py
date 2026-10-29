from django.urls import path
from .views import (
    add_score,
    add_score_for,
    assessment_config_view,
    assessment_hub_view,
    assessment_result,
    attendance_management_view,
    course_assignments_view,
    course_registration_form,
    grade_result,
    registrar_add_results,
    registrar_edit_results,
    registrar_view_transcripts,
    registrar_manage_clearance,
    student_assessment_recap_view,
    student_course_detail_view,
    result_sheet_pdf_view,
    view_transcripts,
)

app_name = "registrar"

urlpatterns = [
    path("assessment-hub/", assessment_hub_view, name="assessment_hub"),
    path("add-score/", add_score, name="add_score"),
    path("grade-results/", grade_result, name="grade_results"),
    path("assessment-results/", assessment_result, name="ass_results"),
    path("assessment-recap/", student_assessment_recap_view, name="student_assessment_recap"),
    path("course/<int:course_id>/assessment/", student_course_detail_view, name="student_course_detail"),
    path("course/<int:course_id>/assessment-config/", assessment_config_view, name="assessment_config"),
    path("course/<int:course_id>/attendance/", attendance_management_view, name="attendance_management"),
    path("course/<int:course_id>/assignments/", course_assignments_view, name="course_assignments"),
    path("registration-form/", course_registration_form, name="course_registration_form"),
    path("edit-results/", registrar_edit_results, name="edit_results"),
    path("view-transcripts/", registrar_view_transcripts, name="view_transcripts"),
    path("manage-clearance/", registrar_manage_clearance, name="manage_clearance"),
    path("result/print/<int:id>/", result_sheet_pdf_view, name="result_sheet_pdf_view"),
    path("manage-score/<int:id>/", add_score_for, name="add_score_for"),
    path("transcripts/", view_transcripts, name="student_transcripts"),
]

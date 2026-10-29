from django.urls import path
from . import views

app_name = 'assignment'

urlpatterns = [
    # Assignment list and detail
    path('<slug>/assignments/', views.assignment_list, name='assignment_list'),
    path('<slug>/assignments/<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('<slug>/assignments/create/', views.assignment_create, name='assignment_create'),
    path('<slug>/assignments/<int:assignment_id>/edit/', views.assignment_edit, name='assignment_edit'),
    path('<slug>/assignments/<int:assignment_id>/delete/', views.assignment_delete, name='assignment_delete'),
    
    # Assignment Groups (weighted grading)
    path('<slug>/assignment-groups/', views.assignment_groups, name='assignment_groups'),
    path('<slug>/assignment-groups/create/', views.assignment_group_create, name='assignment_group_create'),
    path('<slug>/assignment-groups/<int:group_id>/edit/', views.assignment_group_edit, name='assignment_group_edit'),
    path('<slug>/assignment-groups/<int:group_id>/delete/', views.assignment_group_delete, name='assignment_group_delete'),
    
    # Student Groups (for group assignments)
    path('<slug>/student-groups/', views.student_groups, name='student_groups'),
    path('<slug>/student-groups/create/', views.student_group_create, name='student_group_create'),
    path('<slug>/student-groups/<int:group_id>/edit/', views.student_group_edit, name='student_group_edit'),
    path('<slug>/student-groups/<int:group_id>/delete/', views.student_group_delete, name='student_group_delete'),
    
    # Rubrics
    path('<slug>/rubrics/', views.rubric_list, name='rubric_list'),
    path('<slug>/rubrics/create/', views.rubric_create, name='rubric_create'),
    path('<slug>/rubrics/<int:rubric_id>/edit/', views.rubric_edit, name='rubric_edit'),
    path('<slug>/rubrics/<int:rubric_id>/delete/', views.rubric_delete, name='rubric_delete'),
    path('<slug>/rubrics/criterion/<int:criterion_id>/delete/', views.rubric_criterion_delete, name='rubric_criterion_delete'),
    path('<slug>/rubrics/rating/<int:rating_id>/delete/', views.rubric_rating_delete, name='rubric_rating_delete'),
    
    # SpeedGrader
    path('<slug>/assignments/<int:assignment_id>/speedgrader/', views.speedgrader, name='speedgrader'),
    
    # Submission download
    path('submission/<int:submission_id>/download/', views.submission_download, name='submission_download'),
    
    # Grade views
    path('<slug>/grades/', views.grade_overview, name='grade_overview'),
    path('<slug>/grades/export/', views.export_grades, name='export_grades'),
    path('<slug>/my-grades/', views.student_grades, name='student_grades'),
    
    # API endpoints
    path('api/quick-grade/', views.api_quick_grade, name='api_quick_grade'),
    path('api/assignments/<int:assignment_id>/publish/', views.api_publish_assignment, name='api_publish_assignment'),
]

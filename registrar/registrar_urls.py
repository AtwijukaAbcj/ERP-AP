from django.urls import path
from . import views

app_name = 'registrar'

urlpatterns = [
    path('add-results/', views.registrar_add_results, name='add_results'),
    path('edit-results/', views.registrar_edit_results, name='edit_results'),
    path('view-transcripts/', views.registrar_view_transcripts, name='view_transcripts'),
    path('manage-clearance/', views.registrar_manage_clearance, name='manage_clearance'),
]

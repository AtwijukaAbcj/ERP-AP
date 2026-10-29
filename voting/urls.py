# Voting App URLs
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard Home
    path('home/', views.voting_home, name='voting_home'),

    # Student Elections
    path('elections/', views.election_list, name='election_list'),
    path('elections/<int:election_id>/vote/', views.vote_election, name='vote_election'),
    path('elections/<int:election_id>/candidates/', views.manage_election_candidates, name='manage_election_candidates'),
    path('candidates/<int:candidate_id>/edit/', views.edit_candidate, name='edit_candidate'),
    path('elections/add/', views.add_election, name='add_election'),
    path('candidates/add/', views.add_candidate, name='add_candidate'),

    # Opinion Polls
    path('polls/', views.poll_list, name='poll_list'),
    path('polls/<int:poll_id>/vote/', views.vote_poll, name='vote_poll'),
    path('polls/<int:poll_id>/edit/', views.edit_poll, name='edit_poll'),
    path('polls/add/', views.add_poll, name='add_poll'),
    path('polls/results/', views.poll_results_view, name='poll_results'),

    # Results View
    path('results/', views.voting_results, name='voting_results'),
# Class Rep Elections
    path('classrep/elections/', views.class_rep_election_list, name='class_rep_election_list'),
    path('classrep/elections/<int:election_id>/vote/', views.vote_class_rep, name='vote_class_rep'),
    path('classrep/elections/add/', views.add_class_rep_election, name='add_class_rep_election'),
    path('classrep/elections/<int:election_id>/edit/', views.edit_class_rep_election, name='edit_class_rep_election'),
    path('classrep/candidates/add/', views.add_class_rep_candidate, name='add_class_rep_candidate'),
    path('classrep/elections/<int:election_id>/candidates/', views.manage_class_rep_candidates, name='manage_class_rep_candidates'),
    path('classrep/candidates/<int:candidate_id>/edit/', views.edit_class_rep_candidate, name='edit_class_rep_candidate'),
    path('overview/', views.view_all_elections, name='all_elections'),
    path('election/<int:election_id>/toggle/', views.toggle_election_status, name='toggle_election_status'),
    path('all-elections/', views.view_all_elections, name='view_all_elections'),

    path('classrep/election/<int:election_id>/toggle/', views.toggle_classrep_election_status, name='toggle_classrep_election_status'),
    path('poll/<int:poll_id>/toggle/', views.toggle_poll_status, name='toggle_poll_status'),
    path('classrep/elections/all/', views.view_all_classrep_elections, name='view_all_classrep_elections'),
    path("elections/<int:election_id>/edit/", views.edit_election, name="edit_election"),

]

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import Student, User
from core.models import Semester, Session
from course.models import Program
from .views import edit_election
from .models import (
    Candidate,
    ClassRepCandidate,
    ClassRepElection,
    ClassRepVote,
    Choice,
    Election,
    Poll,
    PollVote,
    Vote,
)


@override_settings(LANGUAGE_CODE="en")
class ElectionEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="election-admin",
            email="election-admin@example.com",
            password="test-password",
        )
        self.election = Election.objects.create(
            title="Student Council Election",
            description="Choose student representatives.",
            is_active=False,
        )
        self.program = Program.objects.create(title="Nursing")
        self.student_user = User.objects.create_user(
            username="candidate-one",
            email="candidate-one@example.com",
            password="test-password",
            first_name="First",
            last_name="Candidate",
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
        )
        self.other_student_user = User.objects.create_user(
            username="candidate-two",
            email="candidate-two@example.com",
            password="test-password",
            first_name="Second",
            last_name="Candidate",
        )
        self.other_student = Student.objects.create(
            student=self.other_student_user,
            program=self.program,
        )
        self.url = reverse("edit_election", args=(self.election.pk,))

    def test_edit_election_renders_form_for_superuser(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Election")
        self.assertContains(response, "Student Council Election")
        self.assertContains(response, 'name="title"')

    def test_edit_election_updates_existing_election(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.url,
            {
                "title": "Updated Student Council Election",
                "description": "Choose the new student representatives.",
                "is_active": False,
            },
        )

        self.assertRedirects(response, reverse("view_all_elections"))
        self.election.refresh_from_db()
        self.assertEqual(self.election.title, "Updated Student Council Election")
        self.assertFalse(self.election.is_active)

    def test_edit_election_remains_superuser_only(self):
        regular_user = User.objects.create_user(
            username="regular-user",
            email="regular-user@example.com",
            password="test-password",
        )
        request = RequestFactory().get(self.url)
        request.user = regular_user
        response = edit_election(request, self.election.pk)

        self.assertEqual(response.status_code, 302)

    def test_admin_can_manage_and_edit_candidate_before_voting(self):
        candidate = Candidate.objects.create(
            election=self.election,
            student=self.student,
            manifesto="Original manifesto",
        )
        self.client.force_login(self.admin)

        list_response = self.client.get(
            reverse("manage_election_candidates", args=(self.election.pk,))
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "First Candidate")
        self.assertContains(list_response, reverse("edit_candidate", args=(candidate.pk,)))

        response = self.client.post(
            reverse("edit_candidate", args=(candidate.pk,)),
            {
                "student": self.other_student.pk,
                "manifesto": "Updated manifesto",
            },
        )

        self.assertRedirects(
            response,
            reverse("manage_election_candidates", args=(self.election.pk,)),
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.student, self.other_student)
        self.assertEqual(candidate.manifesto, "Updated manifesto")
        self.assertEqual(candidate.election, self.election)

    def test_candidate_cannot_be_changed_after_voting_starts(self):
        candidate = Candidate.objects.create(
            election=self.election,
            student=self.student,
            manifesto="Original manifesto",
        )
        voter = User.objects.create_user(
            username="voter",
            email="voter@example.com",
            password="test-password",
        )
        Vote.objects.create(
            election=self.election,
            voter=voter,
            candidate=candidate,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("edit_candidate", args=(candidate.pk,)),
            {
                "student": self.other_student.pk,
                "manifesto": "Changed after vote",
            },
        )

        self.assertRedirects(
            response,
            reverse("manage_election_candidates", args=(self.election.pk,)),
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.student, self.student)
        self.assertEqual(candidate.manifesto, "Original manifesto")

    def test_admin_can_edit_class_rep_candidate_before_voting(self):
        session = Session.objects.create(session="2026/2027")
        semester = Semester.objects.create(session=session)
        self.student.semester = semester
        self.student.save(update_fields=["semester"])
        self.other_student.semester = semester
        self.other_student.save(update_fields=["semester"])
        election = ClassRepElection.objects.create(
            title="Nursing Class Representative",
            program=self.program,
            session=session,
            is_active=False,
        )
        candidate = ClassRepCandidate.objects.create(
            election=election,
            student=self.student,
            program=self.program,
            session=session,
            manifesto="Original class manifesto",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("edit_class_rep_candidate", args=(candidate.pk,)),
            {
                "student": self.other_student.pk,
                "manifesto": "Updated class manifesto",
            },
        )

        self.assertRedirects(
            response,
            reverse("manage_class_rep_candidates", args=(election.pk,)),
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.student, self.other_student)
        self.assertEqual(candidate.program, self.program)
        self.assertEqual(candidate.session, session)
        self.assertEqual(candidate.manifesto, "Updated class manifesto")

    def test_class_rep_candidate_cannot_be_changed_after_voting_starts(self):
        session = Session.objects.create(session="2027/2028")
        election = ClassRepElection.objects.create(
            title="Nursing Class Representative",
            program=self.program,
            session=session,
            is_active=True,
        )
        candidate = ClassRepCandidate.objects.create(
            election=election,
            student=self.student,
            program=self.program,
            session=session,
            manifesto="Original class manifesto",
        )
        voter = User.objects.create_user(
            username="class-voter",
            email="class-voter@example.com",
            password="test-password",
        )
        ClassRepVote.objects.create(
            election=election,
            candidate=candidate,
            voter=voter,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("edit_class_rep_candidate", args=(candidate.pk,)),
            {
                "student": self.other_student.pk,
                "manifesto": "Changed after vote",
            },
        )

        self.assertRedirects(
            response,
            reverse("manage_class_rep_candidates", args=(election.pk,)),
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.student, self.student)
        self.assertEqual(candidate.manifesto, "Original class manifesto")

    def test_closed_poll_results_are_hidden_until_voting_closes(self):
        poll = Poll.objects.create(question="Preferred study time?", is_active=True)
        closed_poll = Poll.objects.create(
            question="Closed poll with no votes",
            is_active=False,
        )
        choice = Choice.objects.create(poll=poll, choice_text="Morning")
        Choice.objects.create(poll=poll, choice_text="Evening")
        voter = User.objects.create_user(
            username="poll-voter",
            email="poll-voter@example.com",
            password="test-password",
        )
        PollVote.objects.create(poll=poll, choice=choice, voter=voter)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("poll_results"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, poll.question)
        self.assertContains(response, closed_poll.question)

        poll.is_active = False
        poll.save(update_fields=["is_active"])
        response = self.client.get(reverse("poll_results"))
        self.assertContains(response, poll.question)

    def test_published_results_include_every_closed_election(self):
        closed_election = Election.objects.create(
            title="Closed student election",
            is_active=False,
        )
        Election.objects.create(
            title="Open student election",
            is_active=True,
        )
        session = Session.objects.create(session="2028/2029")
        classrep_election = ClassRepElection.objects.create(
            title="Closed class representative election",
            program=self.program,
            session=session,
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("voting_results"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, closed_election.title)
        self.assertContains(response, classrep_election.title)
        self.assertNotContains(response, "Open student election")

    def test_election_cannot_be_activated_without_two_candidates_or_by_get(self):
        self.client.force_login(self.admin)
        toggle_url = reverse("toggle_election_status", args=(self.election.pk,))

        response = self.client.get(toggle_url)
        self.assertEqual(response.status_code, 405)

        response = self.client.post(toggle_url)
        self.assertRedirects(response, reverse("view_all_elections"))
        self.election.refresh_from_db()
        self.assertFalse(self.election.is_active)

    def test_closed_election_rejects_ballot_access(self):
        self.client.force_login(self.student_user)

        response = self.client.get(
            reverse("vote_election", args=(self.election.pk,))
        )

        self.assertEqual(response.status_code, 404)

    def test_class_rep_vote_requires_matching_session_and_accepts_one_ballot(self):
        session = Session.objects.create(session="2028/2029")
        other_session = Session.objects.create(session="2029/2030")
        semester = Semester.objects.create(session=other_session)
        self.student.semester = semester
        self.student.save(update_fields=["semester"])
        election = ClassRepElection.objects.create(
            title="Nursing Class Representative",
            program=self.program,
            session=session,
            is_active=True,
        )
        candidate = ClassRepCandidate.objects.create(
            election=election,
            student=self.student,
            program=self.program,
            session=session,
        )
        ClassRepCandidate.objects.create(
            election=election,
            student=self.other_student,
            program=self.program,
            session=session,
        )
        self.client.force_login(self.student_user)
        ballot_url = reverse("vote_class_rep", args=(election.pk,))

        ineligible_response = self.client.get(ballot_url)
        self.assertRedirects(
            ineligible_response,
            reverse("class_rep_election_list"),
        )
        self.assertEqual(ClassRepVote.objects.filter(election=election).count(), 0)

        semester.session = session
        semester.save(update_fields=["session"])
        response = self.client.post(
            ballot_url,
            {"candidate": candidate.pk},
        )
        self.assertRedirects(response, reverse("class_rep_election_list"))
        self.assertEqual(ClassRepVote.objects.filter(election=election).count(), 1)

        self.client.post(ballot_url, {"candidate": candidate.pk})
        self.assertEqual(ClassRepVote.objects.filter(election=election).count(), 1)

    def test_poll_vote_is_counted_once_and_closed_poll_has_no_ballot(self):
        poll = Poll.objects.create(question="Preferred study time?", is_active=True)
        choice = Choice.objects.create(poll=poll, choice_text="Morning")
        Choice.objects.create(poll=poll, choice_text="Evening")
        self.client.force_login(self.student_user)
        ballot_url = reverse("vote_poll", args=(poll.pk,))

        response = self.client.post(ballot_url, {"choice": choice.pk})
        self.assertRedirects(response, reverse("poll_list"))
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 1)
        self.assertEqual(PollVote.objects.filter(poll=poll).count(), 1)

        self.client.post(ballot_url, {"choice": choice.pk})
        self.assertEqual(PollVote.objects.filter(poll=poll).count(), 1)
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 1)

        poll.is_active = False
        poll.save(update_fields=["is_active"])
        response = self.client.get(ballot_url)
        self.assertEqual(response.status_code, 404)

    def test_admin_overview_renders_counts_without_join_multiplication(self):
        election = Election.objects.create(
            title="Student Council Election",
            is_active=False,
        )
        first_candidate = Candidate.objects.create(
            election=election,
            student=self.student,
        )
        second_candidate = Candidate.objects.create(
            election=election,
            student=self.other_student,
        )
        Vote.objects.create(
            election=election,
            voter=self.admin,
            candidate=first_candidate,
        )
        Vote.objects.create(
            election=election,
            voter=self.student_user,
            candidate=second_candidate,
        )

        session = Session.objects.create(session="2028/2029")
        classrep_election = ClassRepElection.objects.create(
            title="Nursing Representative",
            program=self.program,
            session=session,
            is_active=False,
        )
        first_classrep_candidate = ClassRepCandidate.objects.create(
            election=classrep_election,
            student=self.student,
            program=self.program,
            session=session,
        )
        second_classrep_candidate = ClassRepCandidate.objects.create(
            election=classrep_election,
            student=self.other_student,
            program=self.program,
            session=session,
        )
        ClassRepVote.objects.create(
            election=classrep_election,
            voter=self.admin,
            candidate=first_classrep_candidate,
        )
        ClassRepVote.objects.create(
            election=classrep_election,
            voter=self.student_user,
            candidate=second_classrep_candidate,
        )

        poll = Poll.objects.create(question="Preferred study time?", is_active=False)
        first_choice = Choice.objects.create(poll=poll, choice_text="Morning")
        second_choice = Choice.objects.create(poll=poll, choice_text="Evening")
        PollVote.objects.create(poll=poll, voter=self.admin, choice=first_choice)
        PollVote.objects.create(
            poll=poll,
            voter=self.student_user,
            choice=second_choice,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("view_all_elections"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["elections"][0].candidate_count, 2)
        self.assertEqual(response.context["elections"][0].vote_count, 2)
        self.assertEqual(
            response.context["classrep_elections"][0].candidate_count,
            2,
        )
        self.assertEqual(
            response.context["classrep_elections"][0].vote_count,
            2,
        )
        self.assertEqual(response.context["polls"][0].choice_count, 2)
        self.assertEqual(response.context["polls"][0].vote_count, 2)

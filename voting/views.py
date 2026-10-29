from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.forms import modelformset_factory
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.views.decorators.http import require_POST

from .models import (
    Election, Candidate, Vote,
    Poll, Choice, PollVote,
    ClassRepElection, ClassRepCandidate, ClassRepVote
)
from .forms import (
    ElectionForm, CandidateForm, VoteForm,
    PollForm, ClassRepElectionForm, ClassRepCandidateForm
)

from accounts.models import Student
from course.models import Program


# ----------------------------------------------------------
# 📌 Dashboard View
# ----------------------------------------------------------
@login_required
def voting_home(request):
    return render(request, 'voting/voting_home.html')


# ----------------------------------------------------------
# 📌 Election Views (General Student Elections)
# ----------------------------------------------------------
@login_required
def election_list(request):
    elections = list(
        Election.objects.filter(is_active=True)
        .annotate(candidate_count=Count("candidates"))
        .order_by("-created_at")
    )
    voted_ids = set(
        Vote.objects.filter(
            election__in=elections,
            voter=request.user,
        ).values_list("election_id", flat=True)
    )
    for election in elections:
        election.has_voted = election.pk in voted_ids
    return render(request, 'voting/election_list.html', {'elections': elections})

@login_required
def vote_election(request, election_id):
    election = get_object_or_404(
        Election.objects.annotate(candidate_count=Count("candidates")),
        id=election_id,
        is_active=True,
    )
    if election.candidate_count < 2:
        messages.error(request, "This election is not ready for voting.")
        return redirect("election_list")

    if Vote.objects.filter(election=election, voter=request.user).exists():
        messages.info(request, "You have already voted in this election.")
        return redirect('election_list')

    if request.method == 'POST':
        form = VoteForm(election, request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    Vote.objects.create(
                        election=election,
                        voter=request.user,
                        candidate=form.cleaned_data['candidate'],
                    )
            except IntegrityError:
                messages.info(request, "You have already voted in this election.")
                return redirect("election_list")
            messages.success(request, "Your vote has been cast.")
            return redirect('election_list')
    else:
        form = VoteForm(election)

    return render(request, 'voting/vote_election.html', {'election': election, 'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_election(request):
    form = ElectionForm(request.POST or None)
    if form.is_valid():
        election = form.save(commit=False)
        election.is_active = False
        election.save()
        messages.success(request, "Election created as a draft. Add at least two candidates, then activate it from the election overview.")
        return redirect('view_all_elections')
    return render(request, 'voting/add_election.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_candidate(request):
    form = CandidateForm(
        request.POST or None,
        request.FILES or None,
        initial={"election": request.GET.get("election")},
    )
    if form.is_valid():
        election = form.cleaned_data["election"]
        if election.is_active or election.vote_set.exists():
            form.add_error(
                "election",
                "Candidates can only be added before the election is activated.",
            )
        elif election.candidates.filter(student=form.cleaned_data["student"]).exists():
            form.add_error("student", "This student is already a candidate in this election.")
        else:
            form.save()
            messages.success(request, "Candidate added successfully.")
            return redirect("manage_election_candidates", election_id=election.pk)
    return render(request, 'voting/add_candidate.html', {'form': form})


# ----------------------------------------------------------
# 📌 Class Rep Voting Views (Tied to Program)
# ----------------------------------------------------------
@login_required
def class_rep_election_list(request):
    student = Student.objects.filter(student=request.user).select_related(
        "semester__session",
    ).first()
    if student and student.semester_id and student.semester.session_id:
        elections = ClassRepElection.objects.filter(
            program=student.program,
            session_id=student.semester.session_id,
            is_active=True,
        ).annotate(candidate_count=Count("candidates")).order_by("-created_at")
        voted_ids = set(
            ClassRepVote.objects.filter(
                election__in=elections,
                voter=request.user,
            ).values_list("election_id", flat=True)
        )
        elections = list(elections)
        for election in elections:
            election.has_voted = election.pk in voted_ids
    else:
        elections = []

    return render(request, 'voting/classrep_election_list.html', {
        'elections': elections,
        'title': 'Class Representative Elections',
    })

@login_required
def vote_class_rep(request, election_id):
    election = get_object_or_404(
        ClassRepElection.objects.annotate(candidate_count=Count("candidates")),
        id=election_id,
        is_active=True,
    )
    student = Student.objects.filter(student=request.user).select_related(
        "semester__session",
    ).first()

    if (
        student is None
        or student.program_id != election.program_id
        or student.semester_id is None
        or student.semester.session_id != election.session_id
    ):
        messages.error(request, "You are not eligible to vote in this election.")
        return redirect('class_rep_election_list')

    if election.candidate_count < 2:
        messages.error(request, "This election is not ready for voting.")
        return redirect("class_rep_election_list")

    if ClassRepVote.objects.filter(election=election, voter=request.user).exists():
        messages.info(request, "You have already voted in this election.")
        return redirect('class_rep_election_list')

    if request.method == 'POST':
        candidate_id = request.POST.get('candidate')
        candidate = get_object_or_404(
            ClassRepCandidate,
            id=candidate_id,
            election=election,
            program=election.program,
            session=election.session,
        )
        try:
            with transaction.atomic():
                ClassRepVote.objects.create(
                    election=election,
                    candidate=candidate,
                    voter=request.user,
                )
        except IntegrityError:
            messages.info(request, "You have already voted in this election.")
            return redirect("class_rep_election_list")
        messages.success(request, "Your vote has been cast.")
        return redirect('class_rep_election_list')

    candidates = ClassRepCandidate.objects.filter(
        election=election,
        program=election.program,
        session=election.session,
    ).select_related("student__student")
    return render(request, 'voting/vote_classrep.html', {
        'election': election,
        'candidates': candidates
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_class_rep_election(request):
    form = ClassRepElectionForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Class representative election created as a draft. Add at least two candidates, then activate it from the election overview.")
        return redirect('view_all_elections')
    return render(request, 'voting/add_class_rep_election.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_class_rep_election(request, election_id):
    election = get_object_or_404(ClassRepElection, pk=election_id)
    if election.is_active or ClassRepVote.objects.filter(election=election).exists():
        messages.error(request, "Only a draft class representative election can be edited.")
        return redirect("view_all_elections")
    form = ClassRepElectionForm(request.POST or None, instance=election)
    if form.is_valid():
        form.save()
        messages.success(request, "Class representative election updated.")
        return redirect("view_all_elections")
    return render(
        request,
        "voting/edit_class_rep_election.html",
        {"form": form, "election": election},
    )

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_class_rep_candidate(request):
    form = ClassRepCandidateForm(
        request.POST or None,
        request.FILES or None,
        initial={"election": request.GET.get("election")},
    )
    if form.is_valid():
        election = form.cleaned_data["election"]
        student = form.cleaned_data["student"]
        if election.is_active or ClassRepVote.objects.filter(election=election).exists():
            form.add_error(
                "election",
                "Candidates can only be added before the election is activated.",
            )
        elif student.program_id != election.program_id:
            form.add_error("student", "The candidate must belong to the election's program.")
        elif (
            student.semester_id is None
            or student.semester.session_id != election.session_id
        ):
            form.add_error("student", "The candidate must belong to the election's session.")
        elif ClassRepCandidate.objects.filter(election=election, student=student).exists():
            form.add_error("student", "This student is already a candidate in this election.")
        else:
            candidate = form.save()
            messages.success(request, "Candidate added successfully.")
            return redirect(
                "manage_class_rep_candidates",
                election_id=candidate.election_id,
            )
    return render(request, 'voting/add_class_rep_candidate.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def manage_election_candidates(request, election_id):
    election = get_object_or_404(Election, pk=election_id)
    return render(
        request,
        "voting/manage_candidates.html",
        {
            "election": election,
            "candidates": election.candidates.select_related("student__student"),
            "is_classrep": False,
            "has_votes": election.is_active or election.vote_set.exists(),
        },
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_candidate(request, candidate_id):
    candidate = get_object_or_404(
        Candidate.objects.select_related("election"),
        pk=candidate_id,
    )
    if candidate.election.is_active or candidate.election.vote_set.exists():
        messages.error(
            request,
            "Candidates can only be edited while the election is a draft.",
        )
        return redirect(
            "manage_election_candidates",
            election_id=candidate.election_id,
        )
    form = CandidateForm(
        request.POST or None,
        request.FILES or None,
        instance=candidate,
    )
    if form.is_valid():
        if candidate.election.candidates.exclude(pk=candidate.pk).filter(
            student=form.cleaned_data["student"]
        ).exists():
            form.add_error("student", "This student is already a candidate in this election.")
        else:
            form.save()
            messages.success(request, "Candidate updated successfully.")
            return redirect(
                "manage_election_candidates",
                election_id=candidate.election_id,
            )
    return render(
        request,
        "voting/edit_candidate.html",
        {"form": form, "candidate": candidate, "is_classrep": False},
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def manage_class_rep_candidates(request, election_id):
    election = get_object_or_404(ClassRepElection, pk=election_id)
    return render(
        request,
        "voting/manage_candidates.html",
        {
            "election": election,
            "candidates": election.candidates.select_related("student__student"),
            "is_classrep": True,
            "has_votes": (
                election.is_active
                or ClassRepVote.objects.filter(election=election).exists()
            ),
        },
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_class_rep_candidate(request, candidate_id):
    candidate = get_object_or_404(
        ClassRepCandidate.objects.select_related("election"),
        pk=candidate_id,
    )
    if candidate.election.is_active or ClassRepVote.objects.filter(election=candidate.election).exists():
        messages.error(
            request,
            "Candidates cannot be edited after voting has started in this election.",
        )
        return redirect(
            "manage_class_rep_candidates",
            election_id=candidate.election_id,
        )
    form = ClassRepCandidateForm(
        request.POST or None,
        request.FILES or None,
        instance=candidate,
    )
    if form.is_valid():
        if form.cleaned_data["student"].program_id != candidate.election.program_id:
            form.add_error("student", "The candidate must belong to the election's program.")
        elif (
            form.cleaned_data["student"].semester_id is None
            or form.cleaned_data["student"].semester.session_id
            != candidate.election.session_id
        ):
            form.add_error("student", "The candidate must belong to the election's session.")
        elif candidate.election.candidates.exclude(pk=candidate.pk).filter(
            student=form.cleaned_data["student"]
        ).exists():
            form.add_error("student", "This student is already a candidate in this election.")
        else:
            form.save()
            messages.success(request, "Candidate updated successfully.")
            return redirect(
                "manage_class_rep_candidates",
                election_id=candidate.election_id,
            )
    return render(
        request,
        "voting/edit_candidate.html",
        {"form": form, "candidate": candidate, "is_classrep": True},
    )


# ----------------------------------------------------------
# 📌 Opinion Poll Views
# ----------------------------------------------------------
@login_required
def poll_list(request):
    polls = list(
        Poll.objects.filter(is_active=True)
        .annotate(choice_count=Count("choices"))
        .order_by("-created_at")
    )
    voted_ids = set(
        PollVote.objects.filter(poll__in=polls, voter=request.user).values_list(
            "poll_id",
            flat=True,
        )
    )
    for poll in polls:
        poll.has_voted = poll.pk in voted_ids
    return render(request, 'voting/poll_list.html', {'polls': polls})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_poll(request):
    ChoiceFormSet = modelformset_factory(Choice, fields=('choice_text',), extra=2, min_num=2, validate_min=True)
    poll_form = PollForm(request.POST or None)
    formset = ChoiceFormSet(request.POST or None, queryset=Choice.objects.none())

    if poll_form.is_valid() and formset.is_valid():
        poll = poll_form.save(commit=False)
        poll.is_active = False
        poll.save()
        for form in formset:
            choice = form.save(commit=False)
            choice.poll = poll
            choice.save()
        messages.success(request, "Poll created as a draft. Add at least two choices, then activate it from the voting overview.")
        return redirect('view_all_elections')

    return render(request, 'voting/add_poll.html', {'poll_form': poll_form, 'formset': formset})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_poll(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    if poll.is_active or PollVote.objects.filter(poll=poll).exists():
        messages.error(request, "Only a draft poll without recorded votes can be edited.")
        return redirect("view_all_elections")
    ChoiceFormSet = modelformset_factory(
        Choice,
        fields=("choice_text",),
        extra=1,
        min_num=2,
        validate_min=True,
        can_delete=True,
    )
    poll_form = PollForm(request.POST or None, instance=poll)
    formset = ChoiceFormSet(
        request.POST or None,
        queryset=poll.choices.all(),
        prefix="choices",
    )
    if poll_form.is_valid() and formset.is_valid():
        poll_form.save()
        for choice_form in formset:
            if choice_form.cleaned_data and not choice_form.cleaned_data.get("DELETE"):
                choice = choice_form.save(commit=False)
                choice.poll = poll
                choice.save()
            elif choice_form.cleaned_data.get("DELETE") and choice_form.instance.pk:
                choice_form.instance.delete()
        messages.success(request, "Draft poll updated.")
        return redirect("view_all_elections")
    return render(
        request,
        "voting/add_poll.html",
        {
            "poll_form": poll_form,
            "formset": formset,
            "poll": poll,
            "is_editing": True,
        },
    )

@login_required
def vote_poll(request, poll_id):
    poll = get_object_or_404(
        Poll.objects.annotate(choice_count=Count("choices")),
        id=poll_id,
        is_active=True,
    )
    if poll.choice_count < 2:
        messages.error(request, "This poll is not ready for voting.")
        return redirect("poll_list")

    if PollVote.objects.filter(poll=poll, voter=request.user).exists():
        messages.info(request, "You have already voted in this poll.")
        return redirect("poll_list")

    if request.method == 'POST':
        choice_id = request.POST.get('choice')
        if choice_id:
            choice = get_object_or_404(Choice, id=choice_id, poll=poll)
            try:
                with transaction.atomic():
                    PollVote.objects.create(
                        poll=poll,
                        choice=choice,
                        voter=request.user,
                    )
                    Choice.objects.filter(pk=choice.pk).update(votes=F("votes") + 1)
            except IntegrityError:
                messages.info(request, "You have already voted in this poll.")
                return redirect("poll_list")
            messages.success(request, "Vote submitted.")
            return redirect('poll_list')

        messages.error(request, "Please select a choice.")
        return redirect("vote_poll", poll_id=poll.pk)

    return render(request, 'voting/vote_poll.html', {'poll': poll})


# ----------------------------------------------------------
# 📌 Voting Results
# ----------------------------------------------------------
@login_required
def voting_results(request):
    election_results = Election.objects.filter(
        is_active=False,
    ).order_by("-created_at").prefetch_related(
        "candidates__student__student",
        "candidates__vote_set",
    )
    classrep_results = ClassRepElection.objects.filter(
        is_active=False,
    ).select_related("program", "session").prefetch_related(
        "candidates__student__student",
        "candidates__classrepvote_set",
    ).order_by("-created_at")
    polls = Poll.objects.filter(
        is_active=False,
    ).prefetch_related("choices").order_by("-created_at")

    return render(request, 'voting/results.html', {
        'elections': election_results,
        "classrep_elections": classrep_results,
        'polls': polls,
    })

@login_required
def poll_results_view(request):
    polls = Poll.objects.filter(
        is_active=False,
    ).prefetch_related("choices").order_by("-created_at")
    return render(request, 'voting/poll_results.html', {'polls': polls})


# ----------------------------------------------------------
# 📌 Admin Overview of All Elections
# ----------------------------------------------------------
@login_required
@user_passes_test(lambda u: u.is_superuser)
def view_all_elections(request):
    elections = Election.objects.annotate(
        candidate_count=Count("candidates", distinct=True),
        vote_count=Count("vote", distinct=True),
    ).order_by("-created_at")
    classrep_elections = ClassRepElection.objects.select_related(
        "program",
        "session",
    ).annotate(
        candidate_count=Count("candidates", distinct=True),
        vote_count=Count("classrepvote", distinct=True),
    ).order_by("-created_at")
    polls = Poll.objects.annotate(
        choice_count=Count("choices", distinct=True),
        vote_count=Count("pollvote", distinct=True),
    ).order_by("-created_at")

    return render(request, 'voting/all_elections.html', {
        'elections': elections,
        'classrep_elections': classrep_elections,
        'polls': polls,
        'title': 'All Elections Overview'
    })

@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_election_status(request, election_id):
    election = get_object_or_404(Election, pk=election_id)
    if not election.is_active:
        if election.candidates.count() < 2:
            messages.error(request, "Add at least two candidates before activating this election.")
            return redirect("view_all_elections")
        if election.vote_set.exists():
            messages.error(request, "An election with recorded votes cannot be reopened.")
            return redirect("view_all_elections")
    election.is_active = not election.is_active
    election.save()
    messages.success(request, f"Election '{election.title}' status updated to {'Active' if election.is_active else 'Closed'}.")
    return redirect('view_all_elections')

@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_classrep_election_status(request, election_id):
    election = get_object_or_404(ClassRepElection, pk=election_id)
    if not election.is_active:
        candidates = election.candidates.filter(
            program=election.program,
            session=election.session,
        )
        if candidates.count() < 2:
            messages.error(request, "Add at least two eligible candidates before activating this election.")
            return redirect("view_all_elections")
        if ClassRepVote.objects.filter(election=election).exists():
            messages.error(request, "An election with recorded votes cannot be reopened.")
            return redirect("view_all_elections")
    election.is_active = not election.is_active
    election.save()
    messages.success(request, f"Class Rep Election for {election.program} status set to {'Active' if election.is_active else 'Closed'}.")
    return redirect('view_all_elections')

@login_required
@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_poll_status(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    if not poll.is_active:
        if poll.choices.count() < 2:
            messages.error(request, "Add at least two choices before activating this poll.")
            return redirect("view_all_elections")
        if PollVote.objects.filter(poll=poll).exists():
            messages.error(request, "A poll with recorded votes cannot be reopened.")
            return redirect("view_all_elections")
    poll.is_active = not poll.is_active
    poll.save()
    messages.success(request, f"Poll '{poll.question}' set to {'Active' if poll.is_active else 'Closed'}.")
    return redirect('view_all_elections')  # or 'poll_list' if preferred

@login_required
@user_passes_test(lambda u: u.is_superuser)
def view_all_classrep_elections(request):
    classrep_elections = ClassRepElection.objects.all().order_by('-created_at')
    return render(request, 'voting/classrep_election_list_all.html', {
        'classrep_elections': classrep_elections,
        'title': 'All Class Rep Elections'
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    if election.is_active or election.vote_set.exists():
        messages.error(request, "Only a draft student election can be edited.")
        return redirect("view_all_elections")
    form = ElectionForm(request.POST or None, instance=election)
    if form.is_valid():
        form.save()
        messages.success(request, "Election updated successfully.")
        return redirect("view_all_elections")
    return render(request, 'voting/edit_election.html', {'form': form, 'election': election})

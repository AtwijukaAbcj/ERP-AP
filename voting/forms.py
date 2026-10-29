from django import forms
from .models import Candidate, Vote
from accounts.models import Student
from django import forms
from .models import Election
from django import forms
from .models import Poll, Choice

from .models import ClassRepElection, ClassRepCandidate


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['election', 'student', 'photo', 'manifesto']
        widgets = {
            "election": forms.Select(attrs={"class": "form-select"}),
            "student": forms.Select(attrs={"class": "form-select"}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "manifesto": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        initial_election = (kwargs.get("initial") or {}).get("election")
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.all()
        if self.instance.pk:
            self.fields["election"].disabled = True
        else:
            self.fields["election"].queryset = Election.objects.filter(
                is_active=False
            ).order_by("-created_at")
            if initial_election:
                self.fields["election"].initial = initial_election

class VoteForm(forms.Form):
    def __init__(self, election, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['candidate'] = forms.ModelChoiceField(
            queryset=Candidate.objects.filter(election=election),
            widget=forms.RadioSelect,
            empty_label=None
        )
        self.fields["candidate"].widget.attrs["class"] = "voting-candidate-radio"



class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'description']
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = ['question']
        widgets = {
            "question": forms.TextInput(attrs={"class": "form-control"}),
        }



class ClassRepElectionForm(forms.ModelForm):
    class Meta:
        model = ClassRepElection
        fields = ['title', 'program', 'session']
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "program": forms.Select(attrs={"class": "form-select"}),
            "session": forms.Select(attrs={"class": "form-select"}),
        }


class ClassRepCandidateForm(forms.ModelForm):
    class Meta:
        model = ClassRepCandidate
        fields = ['student', 'election', 'manifesto', 'photo']  # Removed program and session
        widgets = {
            "student": forms.Select(attrs={"class": "form-select"}),
            "election": forms.Select(attrs={"class": "form-select"}),
            "manifesto": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        initial_election = (kwargs.get("initial") or {}).get("election")
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["election"].queryset = ClassRepElection.objects.filter(
                pk=self.instance.election_id
            )
            self.fields["election"].disabled = True
        else:
            self.fields['election'].queryset = ClassRepElection.objects.filter(
                is_active=False
            ).order_by("-created_at")
            if initial_election:
                self.fields["election"].initial = initial_election

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Auto-set program and session from selected election
        instance.program = instance.election.program
        instance.session = instance.election.session
        if commit:
            instance.save()
        return instance

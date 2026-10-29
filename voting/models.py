from django.db import models
from django.conf import settings
from django.utils import timezone
from accounts.models import Student
from course.models import Program
from core.models import Session
from course.models import Program
# ----------------------------------------------------------------
# 📌 1. Student Elections (General)
# ----------------------------------------------------------------

class Election(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Candidate(models.Model):
    election = models.ForeignKey(Election, related_name='candidates', on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='candidate_photos/', null=True, blank=True)
    manifesto = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.get_full_name} - {self.election.title}"

class Vote(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['election', 'voter'], name='unique_election_voter')
        ]  # prevent multiple votes


# ----------------------------------------------------------------
# 📌 2. Opinion Polls
# ----------------------------------------------------------------

class Poll(models.Model):
    question = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True) 
    def __str__(self):
        return self.question

class Choice(models.Model):
    poll = models.ForeignKey(Poll, related_name='choices', on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.PositiveIntegerField(default=0)


    def __str__(self):
        return self.choice_text

class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['poll', 'voter'], name='unique_poll_voter')
        ]


# ----------------------------------------------------------------
# 📌 3. Class Representative Elections (Per Program)
# ----------------------------------------------------------------

class ClassRepElection(models.Model):
    title = models.CharField(max_length=200)  # ✅ this must exist
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    session = models.ForeignKey('core.Session', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title



class ClassRepCandidate(models.Model):
    election = models.ForeignKey(ClassRepElection, on_delete=models.CASCADE, related_name='candidates')
    student = models.ForeignKey('accounts.Student', on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, editable=False)
    manifesto = models.TextField(blank=True)
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)

    def __str__(self):
        return self.student.get_full_name
class ClassRepVote(models.Model):
    election = models.ForeignKey(ClassRepElection, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ClassRepCandidate, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['election', 'voter'], name='unique_classrep_election_voter')
        ]  # only one vote per student per election

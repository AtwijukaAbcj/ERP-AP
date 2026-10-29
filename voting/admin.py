from django.contrib import admin
from .models import Poll, Choice, Vote, Election, Candidate
from .models import PollVote
from .models import ClassRepElection, ClassRepCandidate, ClassRepVote

# ------------------------------
# Opinion Polls Admin Section
# ------------------------------
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2

class PollAdmin(admin.ModelAdmin):
    list_display = ['question', 'created_at']
    inlines = [ChoiceInline]

# ------------------------------
# Student Elections Admin Section
# ------------------------------
class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 1

class ElectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'created_at']
    inlines = [CandidateInline]

admin.site.register(Election, ElectionAdmin)

# ------------------------------
# Common Models
# ------------------------------
admin.site.register(Candidate)
admin.site.register(Choice)
admin.site.register(Vote)
admin.site.register(Poll, PollAdmin)


admin.site.register(PollVote)


class ClassRepCandidateInline(admin.TabularInline):
    model = ClassRepCandidate
    extra = 1

class ClassRepElectionAdmin(admin.ModelAdmin):
    list_display = ['program', 'is_active', 'created_at']
    inlines = [ClassRepCandidateInline]

admin.site.register(ClassRepElection, ClassRepElectionAdmin)
admin.site.register(ClassRepVote)

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import os

from .models import (
    Assignment, AssignmentGroup, AssignmentSubmission,
    Rubric, RubricCriterion, RubricRating, StudentGroup
)


# ########################################################
# Assignment Group Forms
# ########################################################

class AssignmentGroupForm(forms.ModelForm):
    """Form for creating/editing assignment groups"""
    
    class Meta:
        model = AssignmentGroup
        fields = ['name', 'weight', 'drop_lowest', 'drop_highest', 'position']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Homework, Quizzes, Exams'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'step': 0.01
            }),
            'drop_lowest': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'drop_highest': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }


# ########################################################
# Student Group Forms
# ########################################################

class StudentGroupForm(forms.ModelForm):
    """Form for creating student groups for group assignments"""
    
    class Meta:
        model = StudentGroup
        fields = ['name', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Group name'
            }),
            'members': forms.CheckboxSelectMultiple(),
        }


# ########################################################
# Rubric Forms
# ########################################################

class RubricForm(forms.ModelForm):
    """Form for creating/editing rubrics"""
    
    class Meta:
        model = Rubric
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Rubric title'
            }),
        }


class RubricCriterionForm(forms.ModelForm):
    """Form for rubric criteria"""
    
    class Meta:
        model = RubricCriterion
        fields = ['description', 'points', 'position']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Criterion description'
            }),
            'points': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': 0.5
            }),
            'position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }


class RubricRatingForm(forms.ModelForm):
    """Form for rubric ratings"""
    
    class Meta:
        model = RubricRating
        fields = ['description', 'points', 'position']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Excellent, Good, Fair, Poor'
            }),
            'points': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': 0.5
            }),
            'position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }


# ########################################################
# Assignment Forms
# ########################################################

class AssignmentForm(forms.ModelForm):
    """Form for creating/editing assignments"""
    
    online_entry_text = forms.BooleanField(
        required=False,
        label=_('Text Entry'),
        help_text=_('Students can type their submission')
    )
    online_entry_file = forms.BooleanField(
        required=False,
        label=_('File Upload'),
        help_text=_('Students can upload files')
    )
    online_entry_url = forms.BooleanField(
        required=False,
        label=_('Website URL'),
        help_text=_('Students can submit a URL')
    )
    
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'assignment_type', 'group',
            'submission_type', 'allowed_file_types', 'max_file_size',
            'allowed_attempts', 'grading_type', 'points_possible',
            'rubric', 'linked_quiz', 'is_group_assignment', 'group_category',
            'due_date', 'available_from', 'available_until',
            'accept_late_submissions', 'late_penalty_percent', 'max_late_days',
            'published', 'show_rubric_to_students', 'anonymous_grading'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Assignment title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Instructions for students...'
            }),
            'assignment_type': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'submission_type': forms.Select(attrs={'class': 'form-select'}),
            'allowed_file_types': forms.Select(attrs={'class': 'form-select'}),
            'max_file_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 500
            }),
            'allowed_attempts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'grading_type': forms.Select(attrs={'class': 'form-select'}),
            'points_possible': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': 0.5
            }),
            'rubric': forms.Select(attrs={'class': 'form-select'}),
            'linked_quiz': forms.Select(attrs={'class': 'form-select'}),
            'is_group_assignment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'group_category': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'available_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'available_until': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'accept_late_submissions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'late_penalty_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'step': 0.5
            }),
            'max_late_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_rubric_to_students': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'anonymous_grading': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        
        if course:
            from quiz.models import Quiz
            self.fields['group'].queryset = AssignmentGroup.objects.filter(course=course)
            self.fields['rubric'].queryset = Rubric.objects.filter(
                models.Q(course=course) | models.Q(course__isnull=True)
            )
            self.fields['group_category'].queryset = StudentGroup.objects.filter(course=course)
            self.fields['linked_quiz'].queryset = Quiz.objects.filter(course=course)
            self.fields['linked_quiz'].label = _('Link to Quiz')
            self.fields['linked_quiz'].help_text = _('Link this assignment to a quiz to show auto-graded results')
        
        # Pre-populate online entry options checkboxes
        if self.instance and self.instance.pk:
            options = self.instance.online_entry_options or []
            self.fields['online_entry_text'].initial = 'text' in options
            self.fields['online_entry_file'].initial = 'file' in options
            self.fields['online_entry_url'].initial = 'url' in options
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Build online_entry_options list from checkboxes
        options = []
        if cleaned_data.get('online_entry_text'):
            options.append('text')
        if cleaned_data.get('online_entry_file'):
            options.append('file')
        if cleaned_data.get('online_entry_url'):
            options.append('url')
        
        cleaned_data['online_entry_options'] = options
        
        # Validate dates
        due = cleaned_data.get('due_date')
        available_from = cleaned_data.get('available_from')
        available_until = cleaned_data.get('available_until')
        
        if available_from and due and available_from > due:
            raise ValidationError(_('Available from date must be before due date'))
        
        if available_until and due and available_until < due:
            raise ValidationError(_('Available until date must be after due date'))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.online_entry_options = self.cleaned_data.get('online_entry_options', [])
        if commit:
            instance.save()
        return instance


# ########################################################
# Submission Forms
# ########################################################

class AssignmentSubmissionForm(forms.ModelForm):
    """Form for students to submit assignments"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['text_entry', 'file_upload', 'url_submission']
        widgets = {
            'text_entry': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Enter your response here...'
            }),
            'file_upload': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'url_submission': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        if self.assignment:
            options = self.assignment.online_entry_options or []
            
            # Show only allowed submission types
            if 'text' not in options:
                del self.fields['text_entry']
            if 'file' not in options:
                del self.fields['file_upload']
            if 'url' not in options:
                del self.fields['url_submission']
    
    def clean_file_upload(self):
        file = self.cleaned_data.get('file_upload')
        if not file:
            return file
        
        if self.assignment:
            # Check file size
            max_size = self.assignment.max_file_size * 1024 * 1024  # Convert MB to bytes
            if file.size > max_size:
                raise ValidationError(
                    _('File too large. Maximum size is %(max)s MB.'),
                    params={'max': self.assignment.max_file_size}
                )
            
            # Check file extension
            allowed = self.assignment.get_allowed_extensions()
            if allowed:
                ext = os.path.splitext(file.name)[1].lower()
                if ext not in allowed:
                    raise ValidationError(
                        _('File type not allowed. Allowed types: %(types)s'),
                        params={'types': ', '.join(allowed)}
                    )
        
        return file
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least one submission type is provided
        has_text = cleaned_data.get('text_entry')
        has_file = cleaned_data.get('file_upload')
        has_url = cleaned_data.get('url_submission')
        
        if not any([has_text, has_file, has_url]):
            raise ValidationError(_('Please provide at least one type of submission.'))
        
        return cleaned_data


# ########################################################
# Grading Forms
# ########################################################

class SubmissionGradeForm(forms.ModelForm):
    """Form for grading submissions"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': 0.5
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide feedback to the student...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        if self.assignment:
            self.fields['score'].widget.attrs['max'] = self.assignment.points_possible
            self.fields['score'].help_text = f'Out of {self.assignment.points_possible} points'
    
    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is not None and self.assignment:
            if score < 0:
                raise ValidationError(_('Score cannot be negative'))
            if score > self.assignment.points_possible:
                raise ValidationError(
                    _('Score cannot exceed %(max)s points'),
                    params={'max': self.assignment.points_possible}
                )
        return score


class QuickGradeForm(forms.Form):
    """Quick grade form for SpeedGrader"""
    submission_id = forms.IntegerField(widget=forms.HiddenInput())
    score = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'min': 0,
            'step': 0.5
        })
    )
    feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-sm',
            'rows': 2,
            'placeholder': 'Quick feedback...'
        })
    )


# ########################################################
# Rubric Assessment Form
# ########################################################

class RubricAssessmentForm(forms.Form):
    """Dynamic form for rubric-based grading"""
    
    def __init__(self, *args, **kwargs):
        rubric = kwargs.pop('rubric', None)
        submission = kwargs.pop('submission', None)
        super().__init__(*args, **kwargs)
        
        if rubric:
            from .models import RubricAssessment
            
            for criterion in rubric.criteria.all():
                # Rating selection field
                rating_choices = [('', '---')] + [
                    (r.id, f'{r.description} ({r.points} pts)')
                    for r in criterion.ratings.all()
                ]
                
                self.fields[f'criterion_{criterion.id}_rating'] = forms.ChoiceField(
                    choices=rating_choices,
                    required=False,
                    label=criterion.description,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
                
                # Custom points field (if not using rating)
                self.fields[f'criterion_{criterion.id}_points'] = forms.DecimalField(
                    max_digits=6,
                    decimal_places=2,
                    required=False,
                    min_value=0,
                    max_value=criterion.points,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm',
                        'placeholder': f'0-{criterion.points}'
                    })
                )
                
                # Comments field
                self.fields[f'criterion_{criterion.id}_comments'] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={
                        'class': 'form-control form-control-sm',
                        'rows': 2,
                        'placeholder': 'Comments...'
                    })
                )
                
                # Pre-populate with existing assessment
                if submission:
                    try:
                        assessment = RubricAssessment.objects.get(
                            submission=submission,
                            criterion=criterion
                        )
                        if assessment.rating:
                            self.fields[f'criterion_{criterion.id}_rating'].initial = assessment.rating.id
                        self.fields[f'criterion_{criterion.id}_points'].initial = assessment.points_awarded
                        self.fields[f'criterion_{criterion.id}_comments'].initial = assessment.comments
                    except RubricAssessment.DoesNotExist:
                        pass


# Need to import models for Q query
from django.db import models

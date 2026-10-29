from django import forms
from django.forms.widgets import RadioSelect, Textarea
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _
from django.forms.models import inlineformset_factory
from django.core.validators import FileExtensionValidator
from .models import Question, Quiz, MCQuestion, Choice, FileUploadQuestion, FileSubmission


class QuestionForm(forms.Form):
    def __init__(self, question, *args, **kwargs):
        super(QuestionForm, self).__init__(*args, **kwargs)
        choice_list = [x for x in question.get_choices_list()]
        self.fields["answers"] = forms.ChoiceField(
            choices=choice_list, widget=RadioSelect
        )


class EssayForm(forms.Form):
    def __init__(self, question, *args, **kwargs):
        super(EssayForm, self).__init__(*args, **kwargs)
        self.fields["answers"] = forms.CharField(
            widget=Textarea(attrs={"style": "width:100%"})
        )


class QuizAddForm(forms.ModelForm):
    class Meta:
        model = Quiz
        exclude = []

    questions = forms.ModelMultipleChoiceField(
        queryset=Question.objects.all().select_subclasses(),
        required=False,
        label=_("Questions"),
        widget=FilteredSelectMultiple(verbose_name=_("Questions"), is_stacked=False),
    )

    def __init__(self, *args, **kwargs):
        super(QuizAddForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["questions"].initial = (
                self.instance.question_set.all().select_subclasses()
            )

    def save(self, commit=True):
        quiz = super(QuizAddForm, self).save(commit=False)
        quiz.save()
        quiz.question_set.set(self.cleaned_data["questions"])
        self.save_m2m()
        return quiz


class MCQuestionForm(forms.ModelForm):
    class Meta:
        model = MCQuestion
        exclude = ()


class MCQuestionFormSet(forms.BaseInlineFormSet):
    def clean(self):
        """
        Custom validation for the formset to ensure:
        1. At least two choices are provided and not marked for deletion.
        2. At least one of the choices is marked as correct.
        """
        super().clean()

        # Collect non-deleted forms
        valid_forms = [
            form for form in self.forms if not form.cleaned_data.get("DELETE", True)
        ]

        valid_choices = [
            "choice_text" in form.cleaned_data.keys() for form in valid_forms
        ]
        if not all(valid_choices):
            raise forms.ValidationError("You must add a valid choice name.")

        # If all forms are deleted, raise a validation error
        if len(valid_forms) < 2:
            raise forms.ValidationError("You must provide at least two choices.")

        # Check if at least one of the valid forms is marked as correct
        correct_choices = [
            form.cleaned_data.get("correct", False) for form in valid_forms
        ]

        if not any(correct_choices):
            raise forms.ValidationError("One choice must be marked as correct.")

        if correct_choices.count(True) > 1:
            raise forms.ValidationError("Only one choice must be marked as correct.")


MCQuestionFormSet = inlineformset_factory(
    MCQuestion,
    Choice,
    form=MCQuestionForm,
    formset=MCQuestionFormSet,
    fields=["choice_text", "correct"],
    can_delete=True,
    extra=5,
)


# ########################################################
# File Upload Question Forms
# ########################################################

class FileUploadQuestionForm(forms.ModelForm):
    """Form for creating/editing file upload questions"""
    class Meta:
        model = FileUploadQuestion
        fields = ['content', 'figure', 'explanation', 'allowed_types', 
                  'max_file_size', 'instructions', 'max_score', 'due_date']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter the question/task description...'
            }),
            'figure': forms.FileInput(attrs={'class': 'form-control'}),
            'explanation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explanation shown after grading (optional)'
            }),
            'allowed_types': forms.Select(attrs={'class': 'form-select'}),
            'max_file_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Detailed submission instructions for students...'
            }),
            'max_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 1000
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
        labels = {
            'content': _('Task/Question'),
            'figure': _('Attachment (optional)'),
            'explanation': _('Grading Rubric/Explanation'),
            'allowed_types': _('Allowed File Types'),
            'max_file_size': _('Max File Size (MB)'),
            'instructions': _('Submission Instructions'),
            'max_score': _('Maximum Score'),
            'due_date': _('Due Date'),
        }


class FileSubmissionForm(forms.Form):
    """Form for students to submit files"""
    file = forms.FileField(
        label=_("Upload Your File"),
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.zip,.rar,.jpg,.png,.py,.js'
        })
    )
    
    def __init__(self, question=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.question = question
        if question:
            # Set accept attribute based on allowed file types
            extensions = question.get_allowed_extensions()
            if extensions:
                accept_str = ','.join(extensions)
                self.fields['file'].widget.attrs['accept'] = accept_str
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and self.question:
            # Check file size
            max_size_bytes = self.question.max_file_size * 1024 * 1024  # Convert MB to bytes
            if file.size > max_size_bytes:
                raise forms.ValidationError(
                    _("File size must be under %(max)s MB. Your file is %(size).2f MB.") % {
                        'max': self.question.max_file_size,
                        'size': file.size / (1024 * 1024)
                    }
                )
            
            # Check file extension
            import os
            ext = os.path.splitext(file.name)[1].lower()
            allowed_extensions = self.question.get_allowed_extensions()
            if allowed_extensions and ext not in allowed_extensions:
                raise forms.ValidationError(
                    _("File type not allowed. Allowed types: %(types)s") % {
                        'types': ', '.join(allowed_extensions)
                    }
                )
        return file


class FileSubmissionGradeForm(forms.ModelForm):
    """Form for lecturers to grade file submissions"""
    class Meta:
        model = FileSubmission
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': 'Enter score'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide feedback on the submission...'
            }),
        }
        labels = {
            'score': _('Score'),
            'feedback': _('Feedback'),
        }

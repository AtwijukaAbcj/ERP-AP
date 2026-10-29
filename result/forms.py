from django import forms
from django.utils.translation import gettext_lazy as _
from .models import AssessmentConfig, AttendanceRecord, ClassSession, CourseAssignment, AssignmentSubmission


class AssessmentConfigForm(forms.ModelForm):
    """Form for configuring assessment weights and settings"""
    
    class Meta:
        model = AssessmentConfig
        fields = [
            'assignment_weight', 'assignment_max', 'assignment_enabled',
            'mid_exam_weight', 'mid_exam_max', 'mid_exam_enabled',
            'quiz_weight', 'quiz_max', 'quiz_enabled',
            'attendance_weight', 'attendance_max', 'attendance_enabled',
            'final_exam_weight', 'final_exam_max', 'final_exam_enabled',
            'total_classes',
        ]
        widgets = {
            'assignment_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'assignment_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'assignment_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'mid_exam_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'mid_exam_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'mid_exam_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'quiz_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'quiz_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'quiz_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'attendance_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'attendance_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'attendance_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'final_exam_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'final_exam_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'final_exam_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'total_classes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        total_weight = 0
        
        if cleaned_data.get('assignment_enabled'):
            total_weight += cleaned_data.get('assignment_weight', 0)
        if cleaned_data.get('mid_exam_enabled'):
            total_weight += cleaned_data.get('mid_exam_weight', 0)
        if cleaned_data.get('quiz_enabled'):
            total_weight += cleaned_data.get('quiz_weight', 0)
        if cleaned_data.get('attendance_enabled'):
            total_weight += cleaned_data.get('attendance_weight', 0)
        if cleaned_data.get('final_exam_enabled'):
            total_weight += cleaned_data.get('final_exam_weight', 0)
        
        if total_weight != 100:
            raise forms.ValidationError(
                _('Total weight of enabled components must equal 100%. Currently: %(total)s%%'),
                params={'total': total_weight}
            )
        
        return cleaned_data


class AttendanceRecordForm(forms.ModelForm):
    """Form for recording attendance"""
    
    class Meta:
        model = AttendanceRecord
        fields = ['student', 'date', 'status', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ClassSessionForm(forms.ModelForm):
    """Form for creating class sessions"""
    
    class Meta:
        model = ClassSession
        fields = ['date', 'topic', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter class topic'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Session notes...'}),
        }


class CourseAssignmentForm(forms.ModelForm):
    """Form for creating course assignments"""
    
    class Meta:
        model = CourseAssignment
        fields = ['title', 'description', 'assignment_type', 'max_score', 'due_date', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assignment title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Assignment description...'}),
            'assignment_type': forms.Select(attrs={'class': 'form-select'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AssignmentGradeForm(forms.ModelForm):
    """Form for grading assignment submissions"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Feedback for student...'}),
        }


class BulkAttendanceForm(forms.Form):
    """Form for bulk attendance recording"""
    date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    topic = forms.CharField(
        max_length=255, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Class topic (optional)'})
    )

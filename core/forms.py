from django import forms
from .models import NewsAndEvents, Session, Semester, SEMESTER
from django import forms
from .models import Timetable, TimetableEntry
from .models import Room
from django import forms
from .models import TimetableEntry
import datetime
from .constants import TIME_CHOICES  # ✅ No circular import

# from .views import TIME_CHOICES  

# news and events
class NewsAndEventsForm(forms.ModelForm):
    class Meta:
        model = NewsAndEvents
        fields = (
            "title",
            "summary",
            "posted_as",
            "event_date",
            "semester",
        )
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update({"class": "form-control"})
        self.fields["summary"].widget.attrs.update({"class": "form-control"})
        self.fields["posted_as"].widget.attrs.update({"class": "form-control"})


class SessionForm(forms.ModelForm):
    next_session_begins = forms.DateTimeField(
        widget=forms.TextInput(
            attrs={
                "type": "date",
            }
        ),
        required=True,
    )

    class Meta:
        model = Session
        fields = ["session", "is_current_session", "next_session_begins"]


class SemesterForm(forms.ModelForm):
    semester = forms.CharField(
        widget=forms.Select(
            choices=SEMESTER,
            attrs={
                "class": "browser-default custom-select",
            },
        ),
        label="semester",
    )
    is_current_semester = forms.TypedChoiceField(
        choices=((True, "Yes"), (False, "No")),
        coerce=lambda value: value == "True",
        widget=forms.Select(
            attrs={"class": "browser-default custom-select"}
        ),
        label="is current semester ?",
    )
    session = forms.ModelChoiceField(
        queryset=Session.objects.all(),
        widget=forms.Select(
            attrs={
                "class": "browser-default custom-select",
            }
        ),
        required=True,
    )

    next_semester_begins = forms.DateTimeField(
        widget=forms.TextInput(
            attrs={
                "type": "date",
                "class": "form-control",
            }
        ),
        required=True,
    )

    class Meta:
        model = Semester
        fields = [
            "semester",
            "is_current_semester",
            "session",
            "next_semester_begins",
            "registration_open_date",
            "registration_close_date",
            "add_drop_open_date",
            "add_drop_close_date",
        ]
        widgets = {
            "registration_open_date": forms.DateInput(attrs={"type": "date"}),
            "registration_close_date": forms.DateInput(attrs={"type": "date"}),
            "add_drop_open_date": forms.DateInput(attrs={"type": "date"}),
            "add_drop_close_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        for open_field, close_field in (
            ("registration_open_date", "registration_close_date"),
            ("add_drop_open_date", "add_drop_close_date"),
        ):
            opens = cleaned_data.get(open_field)
            closes = cleaned_data.get(close_field)
            if opens and closes and closes < opens:
                self.add_error(close_field, "The closing date cannot be before the opening date.")
        return cleaned_data


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['program', 'semester', 'academic_year']

TIME_CHOICES = [
    (datetime.time(hour=h, minute=m).strftime('%H:%M'), datetime.time(hour=h, minute=m).strftime('%I:%M %p'))
    for h in range(7, 21)  # 7:00 to 20:30
    for m in (0, 30)
]

class TimetableEntryForm(forms.ModelForm):
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = TimetableEntry
        fields = [
            'timetable', 'course', 'lecturer', 'day',
            'start_time', 'end_time', 'room',
            'is_online', 'meeting_link'
        ]
        widgets = {
            'timetable': forms.HiddenInput(),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'lecturer': forms.Select(attrs={'class': 'form-select'}),
            'day': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'is_online': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'meeting_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Paste Zoom/Meet/Jitsi link'
            }),
        }

class TimetableForm(forms.ModelForm):
    semester = forms.ChoiceField(
        choices=SEMESTER,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )

    academic_year = forms.ChoiceField(
        choices=[
            ("2025/2026", "2025/2026"),
            ("2026/2027", "2026/2027"),
            ("2027/2028", "2027/2028"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )

    class Meta:
        model = Timetable
        fields = ['program', 'semester', 'academic_year']
        widgets = {
            'program': forms.Select(attrs={'class': 'form-select'}),
        }


# Site Settings Form
from .models import SiteSettings

class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'site_tagline', 'logo', 'logo_white', 'favicon',
            'primary_color', 'school_name', 'school_email', 'school_phone',
            'school_address', 'school_website'
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={'class': 'form-control'}),
            'site_tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'school_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'school_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'school_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'school_website': forms.URLInput(attrs={'class': 'form-control'}),
        }

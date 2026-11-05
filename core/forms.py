import base64
import datetime
import logging
import re
from io import BytesIO
from pathlib import PurePath

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from lxml import etree
from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from accounts.models import Role
from .constants import TIME_CHOICES  # ✅ No circular import
from .models import (
    NewsAndEvents,
    Room,
    SEMESTER,
    Semester,
    Session,
    Timetable,
    TimetableEntry,
)

# from .views import TIME_CHOICES  

logger = logging.getLogger(__name__)
MAX_BRANDING_IMAGE_BYTES = 5 * 1024 * 1024
MAX_BRANDING_IMAGE_DIMENSION = 1024
_SVG_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
_SVG_IMPORT_PATTERN = re.compile(r"@import[^;]*;?", re.IGNORECASE)
_SVG_RASTER_DATA_PATTERN = re.compile(
    r"data:image/(?:png|jpeg|gif|webp);base64,([A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)
_SVG_ACTIVE_ELEMENTS = {
    "script",
    "foreignobject",
    "iframe",
    "object",
    "embed",
    "audio",
    "video",
}


def _clean_svg(data):
    if len(data) > MAX_BRANDING_IMAGE_BYTES:
        raise ValidationError(_("SVG logos must be no larger than 5 MB."))
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.IGNORECASE):
        raise ValidationError(_("SVG logos with document types or entities are not supported."))

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise ValidationError(_("Upload a valid SVG logo.")) from exc

    if etree.QName(root).localname.lower() != "svg":
        raise ValidationError(_("Upload a valid SVG logo."))

    for element in list(root.iter()):
        if not isinstance(element.tag, str):
            continue
        local_name = etree.QName(element).localname
        if local_name.lower() in _SVG_ACTIVE_ELEMENTS:
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            continue

        for attribute, value in list(element.attrib.items()):
            attribute_name = etree.QName(attribute).localname.lower()
            if attribute_name.startswith("on"):
                del element.attrib[attribute]
                continue

            if attribute_name in {"href", "src"}:
                if value.startswith("#"):
                    continue
                data_match = (
                    _SVG_RASTER_DATA_PATTERN.fullmatch(value)
                    if local_name.lower() == "image"
                    else None
                )
                if data_match:
                    try:
                        embedded_image = base64.b64decode(
                            re.sub(r"\s+", "", data_match.group(1)),
                            validate=True,
                        )
                        if len(embedded_image) > MAX_BRANDING_IMAGE_BYTES:
                            raise ValueError("Embedded image exceeds the size limit.")
                        with Image.open(BytesIO(embedded_image)) as image:
                            if max(image.size) > 4096:
                                raise ValueError(
                                    "Embedded image dimensions exceed the size limit."
                                )
                            image.verify()
                        continue
                    except (
                        OSError,
                        ValueError,
                        Image.DecompressionBombError,
                    ) as exc:
                        raise ValidationError(
                            _("The SVG contains an invalid embedded image.")
                        ) from exc
                del element.attrib[attribute]
                continue

            if "url(" in value.lower():
                element.attrib[attribute] = _SVG_URL_PATTERN.sub(
                    lambda match: (
                        match.group(0)
                        if match.group(2).strip(" '\"").startswith("#")
                        else "none"
                    ),
                    value,
                )

        if local_name.lower() == "style" and element.text:
            element.text = _SVG_IMPORT_PATTERN.sub("", element.text)
            element.text = _SVG_URL_PATTERN.sub(
                lambda match: (
                    match.group(0)
                    if match.group(2).strip(" '\"").startswith("#")
                    else "none"
                ),
                element.text,
            )

    return etree.tostring(root, encoding="utf-8")


def _svg_to_png(upload):
    safe_svg = _clean_svg(upload.read())
    try:
        drawing = svg2rlg(BytesIO(safe_svg))
        if (
            drawing is None
            or drawing.width <= 0
            or drawing.height <= 0
            or max(drawing.width, drawing.height) > 4096
        ):
            raise ValueError("SVG has invalid or excessive dimensions.")

        dpi = min(
            72,
            72 * MAX_BRANDING_IMAGE_DIMENSION / max(drawing.width, drawing.height),
        )
        png_data = renderPM.drawToString(
            drawing,
            fmt="PNG",
            dpi=dpi,
            backend="rlPyCairo",
        )
    except Exception as exc:
        logger.exception("Could not convert uploaded branding SVG to PNG.")
        raise ValidationError(
            _("This SVG could not be processed. Please upload a PNG or JPEG instead.")
        ) from exc

    filename = PurePath(upload.name).with_suffix(".png").name
    return SimpleUploadedFile(filename, png_data, content_type="image/png")


class BrandingImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "widget",
            forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*,.svg",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        upload = super().clean(data, initial)
        if not upload or isinstance(upload, str):
            return upload
        if upload.size > MAX_BRANDING_IMAGE_BYTES:
            raise ValidationError(_("Logo files must be no larger than 5 MB."))

        sample = upload.read(1024)
        upload.seek(0)
        is_svg = upload.name.lower().endswith(".svg") or (
            b"<svg" in sample.lower()
        )
        if is_svg:
            return _svg_to_png(upload)

        return forms.ImageField(required=False).clean(upload)


# news and events
class NewsAndEventsForm(forms.ModelForm):
    visible_to_roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "searchable-checkbox-input"}
        ),
        label=_("Roles that can see this post"),
        help_text=_("Leave blank to make this post visible to everyone."),
    )

    class Meta:
        model = NewsAndEvents
        fields = (
            "title",
            "summary",
            "posted_as",
            "visible_to_roles",
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
        self.fields["visible_to_roles"].queryset = Role.objects.order_by("name")


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
from .models import EmailServerSettings, SiteSettings

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


class BrandingSettingsForm(SiteSettingsForm):
    logo = BrandingImageField(label=_("Logo"))
    logo_white = BrandingImageField(label=_("Logo white"))
    favicon = BrandingImageField(label=_("Favicon"))

    class Meta(SiteSettingsForm.Meta):
        fields = [
            "site_name",
            "site_tagline",
            "logo",
            "logo_white",
            "favicon",
            "primary_color",
        ]


class SchoolInformationSettingsForm(SiteSettingsForm):
    class Meta(SiteSettingsForm.Meta):
        fields = [
            "school_name",
            "school_email",
            "school_phone",
            "school_address",
            "school_website",
        ]


class StudentIdentifierSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ("student_registration_number_format",)
        widgets = {
            "student_registration_number_format": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            ),
        }

    def clean_student_registration_number_format(self):
        from accounts.identifiers import (
            REGISTRATION_NUMBER_FORMAT_DEFAULT,
            validate_registration_number_format,
        )

        value = self.cleaned_data["student_registration_number_format"].strip()
        return validate_registration_number_format(
            value or REGISTRATION_NUMBER_FORMAT_DEFAULT
        )


class EmailServerSettingsForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
        help_text="Leave blank to keep the current password.",
    )

    class Meta:
        model = EmailServerSettings
        fields = [
            "host",
            "port",
            "username",
            "use_tls",
            "use_ssl",
            "from_email",
            "from_name",
            "is_enabled",
        ]
        widgets = {
            "host": forms.TextInput(attrs={"class": "form-control"}),
            "port": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 65535}
            ),
            "username": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "use_tls": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "use_ssl": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "from_email": forms.EmailInput(attrs={"class": "form-control"}),
            "from_name": forms.TextInput(attrs={"class": "form-control"}),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_enabled"].label = "Use dashboard email settings"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_enabled") and not cleaned_data.get("host"):
            self.add_error(
                "host",
                "Enter an SMTP host before enabling dashboard email settings.",
            )
        if cleaned_data.get("use_tls") and cleaned_data.get("use_ssl"):
            raise forms.ValidationError(
                "Choose either TLS or SSL; they cannot both be enabled."
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            instance.set_password(password)
        if commit:
            instance.save()
        return instance

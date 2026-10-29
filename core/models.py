from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


NEWS = _("News")
EVENTS = _("Event")

POST = (
    (NEWS, _("News")),
    (EVENTS, _("Event")),
)

FIRST = _("First")
SECOND = _("Second")
THIRD = _("Third")

SEMESTER = (
    (FIRST, _("First")),
    (SECOND, _("Second")),
    (THIRD, _("Third")),
)


class NewsAndEventsQuerySet(models.query.QuerySet):
    def search(self, query):
        lookups = (
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(posted_as__icontains=query)
        )
        return self.filter(lookups).distinct()


class NewsAndEventsManager(models.Manager):
    def get_queryset(self):
        return NewsAndEventsQuerySet(self.model, using=self._db)

    def all(self):
        return self.get_queryset()

    def get_by_id(self, id):
        qs = self.get_queryset().filter(
            id=id
        )  # NewsAndEvents.objects == self.get_queryset()
        if qs.count() == 1:
            return qs.first()
        return None

    def search(self, query):
        return self.get_queryset().search(query)


class NewsAndEvents(models.Model):
    title = models.CharField(max_length=200, null=True)
    summary = models.TextField(max_length=200, blank=True, null=True)
    posted_as = models.CharField(choices=POST, max_length=10)
    event_date = models.DateField(null=True, blank=True)
    semester = models.ForeignKey(
        "Semester",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="news_and_events",
    )
    updated_date = models.DateTimeField(auto_now=True, auto_now_add=False, null=True)
    upload_time = models.DateTimeField(auto_now=False, auto_now_add=True, null=True)

    objects = NewsAndEventsManager()

    def __str__(self):
        return f"{self.title}"


class Session(models.Model):
    session = models.CharField(max_length=200, unique=True)
    is_current_session = models.BooleanField(default=False, blank=True, null=True)
    next_session_begins = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.session}"


class Semester(models.Model):
    semester = models.CharField(max_length=10, choices=SEMESTER, blank=True)
    is_current_semester = models.BooleanField(default=False, blank=True, null=True)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, blank=True, null=True
    )
    next_semester_begins = models.DateField(null=True, blank=True)
    registration_open_date = models.DateField(null=True, blank=True)
    registration_close_date = models.DateField(null=True, blank=True)
    add_drop_open_date = models.DateField(null=True, blank=True)
    add_drop_close_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.semester}"


class ActivityLog(models.Model):
    message = models.TextField()
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.created_at}]{self.message}"



# =========================
# Timetable Related Models
# =========================

class Room(models.Model):
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()

    def __str__(self):
        return self.name

class Timetable(models.Model):
    program = models.ForeignKey('course.Program', on_delete=models.CASCADE)
    semester = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=9)  # e.g. 2024/2025

    def __str__(self):
        return f"{self.program} - {self.semester} - {self.academic_year}"

class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    course = models.ForeignKey('course.Course', on_delete=models.CASCADE)
    lecturer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, limit_choices_to={'is_lecturer': True})
    day = models.CharField(max_length=10, choices=[
        ('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday')
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    is_online = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True, null=True, help_text="Paste Zoom/Meet/Jitsi link")
    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.course.title} on {self.day} ({self.start_time}-{self.end_time})"


# =========================
# Site Settings Model
# =========================

class SiteSettings(models.Model):
    """Singleton model for site-wide settings"""
    site_name = models.CharField(max_length=100, default="FalconLMS")
    site_tagline = models.CharField(max_length=200, default="Learning Management System", blank=True)
    logo = models.ImageField(upload_to='site/', blank=True, null=True, help_text="Upload school logo")
    logo_white = models.ImageField(upload_to='site/', blank=True, null=True, help_text="Upload white/light version of logo for dark backgrounds")
    favicon = models.ImageField(upload_to='site/', blank=True, null=True, help_text="Upload favicon (32x32 recommended)")
    primary_color = models.CharField(max_length=7, default="#914c77", help_text="Primary theme color (hex)")
    school_name = models.CharField(max_length=200, default="Unity College", blank=True)
    school_email = models.EmailField(default="info@school.edu", blank=True)
    school_phone = models.CharField(max_length=50, blank=True)
    school_address = models.TextField(blank=True)
    school_website = models.URLField(blank=True)
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return self.site_name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SiteSettings.objects.exists():
            raise ValueError("Only one SiteSettings instance is allowed")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get the singleton settings instance, create if doesn't exist"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

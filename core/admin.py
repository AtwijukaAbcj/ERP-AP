from django.contrib import admin
from .models import Session, Semester, NewsAndEvents, SiteSettings

from django.contrib import admin
from .models import Timetable, TimetableEntry, Room


class NewsAndEventsAdmin(admin.ModelAdmin):
    pass


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'school_name', 'school_email')
    fieldsets = (
        ('Branding', {
            'fields': ('site_name', 'site_tagline', 'logo', 'logo_white', 'favicon', 'primary_color')
        }),
        ('School Information', {
            'fields': ('school_name', 'school_email', 'school_phone', 'school_address', 'school_website')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow adding if no instance exists
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Semester)
admin.site.register(Session)
admin.site.register(NewsAndEvents, NewsAndEventsAdmin)

admin.site.register(Timetable)
admin.site.register(TimetableEntry)
admin.site.register(Room)

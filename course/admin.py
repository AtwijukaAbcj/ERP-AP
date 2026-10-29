from django.contrib import admin
from django.contrib.auth.models import Group

from .models import Program, Course, CourseAllocation, CourseOffer, Upload

class ProgramAdmin(admin.ModelAdmin):
    pass

class CourseAdmin(admin.ModelAdmin):
    pass

class UploadAdmin(admin.ModelAdmin):
    pass

admin.site.register(Program, ProgramAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(CourseAllocation)
admin.site.register(Upload, UploadAdmin)


@admin.register(CourseOffer)
class CourseOfferAdmin(admin.ModelAdmin):
    list_display = ("dep_head", "semester")
    list_filter = ("semester",)
    filter_horizontal = ("courses",)

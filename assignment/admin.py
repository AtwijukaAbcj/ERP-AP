from django.contrib import admin
from .models import (
    Assignment, AssignmentGroup, AssignmentSubmission,
    Rubric, RubricCriterion, RubricRating, RubricAssessment,
    StudentGroup
)


class RubricCriterionInline(admin.TabularInline):
    model = RubricCriterion
    extra = 1


class RubricRatingInline(admin.TabularInline):
    model = RubricRating
    extra = 1


@admin.register(AssignmentGroup)
class AssignmentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'weight', 'position', 'drop_lowest')
    list_filter = ('course',)
    search_fields = ('name', 'course__title')
    ordering = ('course', 'position')


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'get_member_count', 'created_at')
    list_filter = ('course',)
    search_fields = ('name',)
    filter_horizontal = ('members',)
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = 'Members'


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'created_by', 'total_points', 'created_at')
    list_filter = ('course',)
    search_fields = ('title',)
    inlines = [RubricCriterionInline]


@admin.register(RubricCriterion)
class RubricCriterionAdmin(admin.ModelAdmin):
    list_display = ('description', 'rubric', 'points', 'position')
    list_filter = ('rubric',)
    inlines = [RubricRatingInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'assignment_type', 'grading_type', 
                    'points_possible', 'due_date', 'published')
    list_filter = ('course', 'assignment_type', 'grading_type', 'published', 
                   'is_group_assignment')
    search_fields = ('title', 'description')
    date_hierarchy = 'due_date'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('course', 'group', 'title', 'description', 'assignment_type')
        }),
        ('Submission Settings', {
            'fields': ('submission_type', 'online_entry_options', 'allowed_file_types',
                      'max_file_size', 'allowed_attempts')
        }),
        ('Grading', {
            'fields': ('grading_type', 'points_possible', 'rubric')
        }),
        ('Group Assignment', {
            'fields': ('is_group_assignment', 'group_category'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('due_date', 'available_from', 'available_until')
        }),
        ('Late Policy', {
            'fields': ('accept_late_submissions', 'late_penalty_percent', 'max_late_days'),
            'classes': ('collapse',)
        }),
        ('Display', {
            'fields': ('published', 'show_rubric_to_students', 'anonymous_grading')
        }),
    )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'status', 'score', 'submitted_at', 
                    'graded_at')
    list_filter = ('status', 'assignment__course', 'assignment')
    search_fields = ('student__student__username', 'assignment__title')
    readonly_fields = ('submitted_at', 'file_size', 'graded_at')
    date_hierarchy = 'submitted_at'


@admin.register(RubricAssessment)
class RubricAssessmentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'criterion', 'rating', 'points_awarded')
    list_filter = ('criterion__rubric',)

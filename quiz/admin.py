from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _
from .models import (
    Quiz,
    Progress,
    Question,
    MCQuestion,
    Choice,
    EssayQuestion,
    Sitting,
    FileUploadQuestion,
    FileSubmission,
)


class ChoiceInline(admin.TabularInline):
    model = Choice


class QuizAdminForm(forms.ModelForm):
    questions = forms.ModelMultipleChoiceField(
        queryset=Question.objects.all().select_subclasses(),
        required=False,
        label=_("Questions"),
        widget=FilteredSelectMultiple(verbose_name=_("Questions"), is_stacked=False),
    )

    class Meta:
        model = Quiz
        fields = ["title", "description"]

    def __init__(self, *args, **kwargs):
        super(QuizAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["questions"].initial = (
                self.instance.question_set.all().select_subclasses()
            )

    def save(self, commit=True):
        quiz = super(QuizAdminForm, self).save(commit=False)
        quiz.save()
        quiz.question_set.set(self.cleaned_data["questions"])
        self.save_m2m()
        return quiz


class QuizAdmin(admin.ModelAdmin):
    form = QuizAdminForm
    fields = (
        "title",
        "description",
        "course",
        "category",
        "random_order",
        "answers_at_end",
        "exam_paper",
        "single_attempt",
        "pass_mark",
        "draft",
    )
    list_display = ("title", "course", "category", "draft")
    search_fields = ("title", "description",)
    # form = QuizAdminForm
    # fields = (
    #     "title",
    #     "description",
    # )
    # list_display = ("title",)
    # # list_filter = ('category',)
    # search_fields = (
    #     "description",
    #     "category",
    # )


class MCQuestionAdmin(admin.ModelAdmin):
    list_display = ("content",)
    # list_filter = ('category',)
    fieldsets = [
        ("figure" "quiz" "choice_order", {"fields": ("content", "explanation")})
    ]

    search_fields = ("content", "explanation")
    filter_horizontal = ("quiz",)

    inlines = [ChoiceInline]


class ProgressAdmin(admin.ModelAdmin):
    search_fields = (
        "user",
        "score",
    )


class EssayQuestionAdmin(admin.ModelAdmin):
    list_display = ("content",)
    # list_filter = ('category',)
    fields = (
        "content",
        "quiz",
        "explanation",
    )
    search_fields = ("content", "explanation")
    filter_horizontal = ("quiz",)


class FileUploadQuestionAdmin(admin.ModelAdmin):
    list_display = ("content", "allowed_types", "max_file_size", "max_score", "due_date")
    list_filter = ("allowed_types",)
    fields = (
        "content",
        "quiz",
        "figure",
        "explanation",
        "allowed_types",
        "max_file_size",
        "instructions",
        "max_score",
        "due_date",
    )
    search_fields = ("content", "instructions")
    filter_horizontal = ("quiz",)


class FileSubmissionAdmin(admin.ModelAdmin):
    list_display = ("question", "sitting", "original_filename", "file_size", "score", "graded_at")
    list_filter = ("graded_at",)
    search_fields = ("original_filename", "sitting__user__email")
    readonly_fields = ("submitted_at", "file_size")


admin.site.register(Quiz, QuizAdmin)
admin.site.register(MCQuestion, MCQuestionAdmin)
admin.site.register(Progress, ProgressAdmin)
admin.site.register(EssayQuestion, EssayQuestionAdmin)
admin.site.register(FileUploadQuestion, FileUploadQuestionAdmin)
admin.site.register(FileSubmission, FileSubmissionAdmin)
admin.site.register(Sitting)

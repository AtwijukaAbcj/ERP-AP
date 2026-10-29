from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.http import JsonResponse, FileResponse

from accounts.decorators import lecturer_required
from .forms import (
    EssayForm,
    MCQuestionForm,
    MCQuestionFormSet,
    QuestionForm,
    QuizAddForm,
    FileUploadQuestionForm,
    FileSubmissionForm,
    FileSubmissionGradeForm,
)
from .models import (
    Course,
    EssayQuestion,
    MCQuestion,
    Progress,
    Question,
    Quiz,
    Sitting,
    FileUploadQuestion,
    FileSubmission,
)


# ########################################################
# Quiz Views
# ########################################################


@method_decorator([login_required, lecturer_required], name="dispatch")
class QuizCreateView(CreateView):
    model = Quiz
    form_class = QuizAddForm
    template_name = "quiz/quiz_form.html"

    def get_initial(self):
        initial = super().get_initial()
        course = get_object_or_404(Course, slug=self.kwargs["slug"])
        initial["course"] = course
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = get_object_or_404(Course, slug=self.kwargs["slug"])
        return context

    def form_valid(self, form):
        form.instance.course = get_object_or_404(Course, slug=self.kwargs["slug"])
        with transaction.atomic():
            self.object = form.save()
            return redirect(
                "question_type_select", slug=self.kwargs["slug"], quiz_id=self.object.id
            )


@method_decorator([login_required, lecturer_required], name="dispatch")
class QuizUpdateView(UpdateView):
    model = Quiz
    form_class = QuizAddForm
    template_name = "quiz/quiz_form.html"

    def get_object(self, queryset=None):
        return get_object_or_404(Quiz, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = get_object_or_404(Course, slug=self.kwargs["slug"])
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            return redirect("quiz_index", self.kwargs["slug"])


@login_required
@lecturer_required
def quiz_delete(request, slug, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    quiz.delete()
    messages.success(request, "Quiz successfully deleted.")
    return redirect("quiz_index", slug=slug)


@login_required
def quiz_list(request, slug):
    course = get_object_or_404(Course, slug=slug)
    quizzes = Quiz.objects.filter(course=course).order_by("-timestamp")
    return render(
        request, "quiz/quiz_list.html", {"quizzes": quizzes, "course": course}
    )


# ########################################################
# Multiple Choice Question Views
# ########################################################


@method_decorator([login_required, lecturer_required], name="dispatch")
class MCQuestionCreate(CreateView):
    model = MCQuestion
    form_class = MCQuestionForm
    template_name = "quiz/mcquestion_form.html"

    # def get_form_kwargs(self):
    #     kwargs = super().get_form_kwargs()
    #     kwargs["quiz"] = get_object_or_404(Quiz, id=self.kwargs["quiz_id"])
    #     return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = get_object_or_404(Course, slug=self.kwargs["slug"])
        context["quiz_obj"] = get_object_or_404(Quiz, id=self.kwargs["quiz_id"])
        context["quiz_questions_count"] = Question.objects.filter(
            quiz=self.kwargs["quiz_id"]
        ).count()
        if self.request.method == "POST":
            context["formset"] = MCQuestionFormSet(self.request.POST)
        else:
            context["formset"] = MCQuestionFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if formset.is_valid():
            with transaction.atomic():
                # Save the MCQuestion instance without committing to the database yet
                self.object = form.save(commit=False)
                self.object.save()

                # Retrieve the Quiz instance
                quiz = get_object_or_404(Quiz, id=self.kwargs["quiz_id"])

                # set the many-to-many relationship
                self.object.quiz.add(quiz)

                # Save the formset (choices for the question)
                formset.instance = self.object
                formset.save()

                if "another" in self.request.POST:
                    return redirect(
                        "mc_create",
                        slug=self.kwargs["slug"],
                        quiz_id=self.kwargs["quiz_id"],
                    )
                return redirect("quiz_index", slug=self.kwargs["slug"])
        else:
            return self.form_invalid(form)


# ########################################################
# Quiz Progress and Marking Views
# ########################################################


@method_decorator([login_required], name="dispatch")
class QuizUserProgressView(TemplateView):
    template_name = "quiz/progress.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        progress, _ = Progress.objects.get_or_create(user=self.request.user)
        context["cat_scores"] = progress.list_all_cat_scores
        context["exams"] = progress.show_exams()
        context["exams_counter"] = context["exams"].count()
        return context


@method_decorator([login_required, lecturer_required], name="dispatch")
class QuizMarkingList(ListView):
    model = Sitting
    template_name = "quiz/quiz_marking_list.html"

    def get_queryset(self):
        queryset = Sitting.objects.filter(complete=True)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(
                quiz__course__allocated_course__lecturer__pk=self.request.user.id
            )
        quiz_filter = self.request.GET.get("quiz_filter")
        if quiz_filter:
            queryset = queryset.filter(quiz__title__icontains=quiz_filter)
        user_filter = self.request.GET.get("user_filter")
        if user_filter:
            queryset = queryset.filter(user__username__icontains=user_filter)
        return queryset


@method_decorator([login_required, lecturer_required], name="dispatch")
class QuizMarkingDetail(DetailView):
    model = Sitting
    template_name = "quiz/quiz_marking_detail.html"

    def post(self, request, *args, **kwargs):
        sitting = self.get_object()
        question_id = request.POST.get("qid")
        if question_id:
            question = Question.objects.get_subclass(id=int(question_id))
            if int(question_id) in sitting.get_incorrect_questions:
                sitting.remove_incorrect_question(question)
            else:
                sitting.add_incorrect_question(question)
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["questions"] = self.object.get_questions(with_answers=True)
        return context


# ########################################################
# Quiz Taking View
# ########################################################


@method_decorator([login_required], name="dispatch")
class QuizTake(FormView):
    form_class = QuestionForm
    template_name = "quiz/question.html"
    result_template_name = "quiz/result.html"

    def dispatch(self, request, *args, **kwargs):
        self.quiz = get_object_or_404(Quiz, slug=self.kwargs["slug"])
        self.course = get_object_or_404(Course, pk=self.kwargs["pk"])
        if not Question.objects.filter(quiz=self.quiz).exists():
            messages.warning(request, "This quiz has no questions available.")
            return redirect("quiz_index", slug=self.course.slug)

        self.sitting = Sitting.objects.user_sitting(
            request.user, self.quiz, self.course
        )
        if not self.sitting:
            messages.info(
                request,
                "You have already completed this quiz. Only one attempt is permitted.",
            )
            return redirect("quiz_index", slug=self.course.slug)

        # Set self.question and self.progress here
        self.question = self.sitting.get_first_question()
        self.progress = self.sitting.progress()

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["question"] = self.question
        return kwargs

    def get_form_class(self):
        if isinstance(self.question, EssayQuestion):
            return EssayForm
        elif isinstance(self.question, FileUploadQuestion):
            return FileSubmissionForm
        return self.form_class
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if isinstance(self.question, FileUploadQuestion):
            kwargs['question'] = self.question
        else:
            kwargs['question'] = self.question
        return kwargs

    def form_valid(self, form):
        # Handle file upload questions differently
        if isinstance(self.question, FileUploadQuestion):
            return self.handle_file_upload(form)
        
        self.form_valid_user(form)
        if not self.sitting.get_first_question():
            return self.final_result_user()
        return super().get(self.request)
    
    def handle_file_upload(self, form):
        """Handle file upload submissions"""
        uploaded_file = form.cleaned_data.get('file')
        if uploaded_file:
            # Create or update file submission
            FileSubmission.objects.update_or_create(
                sitting=self.sitting,
                question=self.question,
                defaults={
                    'file': uploaded_file,
                    'original_filename': uploaded_file.name,
                    'file_size': uploaded_file.size,
                }
            )
            # Store reference in user answers
            self.sitting.add_user_answer(self.question, f"file:{uploaded_file.name}")
        
        self.sitting.remove_first_question()
        self.question = self.sitting.get_first_question()
        self.progress = self.sitting.progress()
        
        if not self.sitting.get_first_question():
            return self.final_result_user()
        return super().get(self.request)

    def form_valid_user(self, form):
        progress, _ = Progress.objects.get_or_create(user=self.request.user)
        guess = form.cleaned_data["answers"]
        is_correct = self.question.check_if_correct(guess)

        if is_correct:
            self.sitting.add_to_score(1)
            progress.update_score(self.question, 1, 1)
        else:
            self.sitting.add_incorrect_question(self.question)
            progress.update_score(self.question, 0, 1)

        if not self.quiz.answers_at_end:
            self.previous = {
                "previous_answer": guess,
                "previous_outcome": is_correct,
                "previous_question": self.question,
                "answers": self.question.get_choices(),
                "question_type": {self.question.__class__.__name__: True},
            }
        else:
            self.previous = {}

        self.sitting.add_user_answer(self.question, guess)
        self.sitting.remove_first_question()

        # Update self.question and self.progress for the next question
        self.question = self.sitting.get_first_question()
        self.progress = self.sitting.progress()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question"] = self.question
        context["quiz"] = self.quiz
        context["course"] = self.course
        context["is_file_upload"] = isinstance(self.question, FileUploadQuestion)
        if hasattr(self, "previous"):
            context["previous"] = self.previous
        if hasattr(self, "progress"):
            context["progress"] = self.progress
        return context

    def final_result_user(self):
        self.sitting.mark_quiz_complete()
        results = {
            "course": self.course,
            "quiz": self.quiz,
            "score": self.sitting.get_current_score,
            "max_score": self.sitting.get_max_score,
            "percent": self.sitting.get_percent_correct,
            "sitting": self.sitting,
            "previous": getattr(self, "previous", {}),
        }

        if self.quiz.answers_at_end:
            results["questions"] = self.sitting.get_questions(with_answers=True)
            results["incorrect_questions"] = self.sitting.get_incorrect_questions

        if (
            not self.quiz.exam_paper
            or self.request.user.is_superuser
            or self.request.user.is_lecturer
        ):
            self.sitting.delete()

        return render(self.request, self.result_template_name, results)


# ########################################################
# File Upload Question Views
# ########################################################

@method_decorator([login_required, lecturer_required], name="dispatch")
class FileUploadQuestionCreate(CreateView):
    """Create a file upload question for a quiz"""
    model = FileUploadQuestion
    form_class = FileUploadQuestionForm
    template_name = "quiz/file_question_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["course"] = get_object_or_404(Course, slug=self.kwargs["slug"])
        context["quiz_obj"] = get_object_or_404(Quiz, id=self.kwargs["quiz_id"])
        context["quiz_questions_count"] = Question.objects.filter(
            quiz=self.kwargs["quiz_id"]
        ).count()
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.save()
            
            quiz = get_object_or_404(Quiz, id=self.kwargs["quiz_id"])
            self.object.quiz.add(quiz)
            
            if "another" in self.request.POST:
                return redirect(
                    "file_question_create",
                    slug=self.kwargs["slug"],
                    quiz_id=self.kwargs["quiz_id"],
                )
            return redirect("quiz_index", slug=self.kwargs["slug"])


@login_required
@lecturer_required
def file_submission_list(request, slug, quiz_id):
    """View all file submissions for a quiz"""
    course = get_object_or_404(Course, slug=slug)
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Get all file upload questions for this quiz
    file_questions = FileUploadQuestion.objects.filter(quiz=quiz)
    
    # Get all submissions grouped by question
    submissions_by_question = []
    for question in file_questions:
        submissions = FileSubmission.objects.filter(
            question=question,
            sitting__quiz=quiz
        ).select_related('sitting__user', 'graded_by')
        
        graded_count = submissions.filter(score__isnull=False).count()
        total_count = submissions.count()
        
        submissions_by_question.append({
            'question': question,
            'submissions': submissions,
            'graded_count': graded_count,
            'total_count': total_count,
        })
    
    context = {
        'title': f'File Submissions - {quiz.title}',
        'course': course,
        'quiz': quiz,
        'submissions_by_question': submissions_by_question,
    }
    return render(request, 'quiz/file_submission_list.html', context)


@login_required
@lecturer_required
def file_submission_grade(request, slug, submission_id):
    """Grade a single file submission"""
    submission = get_object_or_404(FileSubmission, id=submission_id)
    course = get_object_or_404(Course, slug=slug)
    
    if request.method == 'POST':
        form = FileSubmissionGradeForm(request.POST, instance=submission)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.graded_by = request.user
            submission.graded_at = timezone.now()
            submission.save()
            messages.success(request, 'Submission graded successfully!')
            return redirect('file_submission_list', slug=slug, quiz_id=submission.sitting.quiz.id)
    else:
        form = FileSubmissionGradeForm(instance=submission)
    
    context = {
        'title': f'Grade Submission',
        'course': course,
        'submission': submission,
        'form': form,
        'question': submission.question,
    }
    return render(request, 'quiz/file_submission_grade.html', context)


@login_required
@lecturer_required
def file_submission_download(request, submission_id):
    """Download a submitted file"""
    submission = get_object_or_404(FileSubmission, id=submission_id)
    return FileResponse(submission.file, as_attachment=True, filename=submission.original_filename)


@login_required
@lecturer_required
def question_type_select(request, slug, quiz_id):
    """Select question type before adding"""
    course = get_object_or_404(Course, slug=slug)
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    context = {
        'title': f'Add Question - {quiz.title}',
        'course': course,
        'quiz': quiz,
        'question_count': Question.objects.filter(quiz=quiz).count(),
    }
    return render(request, 'quiz/question_type_select.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404
from django.utils import timezone
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.utils.decorators import method_decorator
from decimal import Decimal

from course.models import Course
from accounts.models import Student
from accounts.decorators import lecturer_required, admin_required

from .models import (
    Assignment, AssignmentGroup, AssignmentSubmission,
    Rubric, RubricCriterion, RubricRating, RubricAssessment,
    StudentGroup, CourseGradeCalculator
)
from .forms import (
    AssignmentForm, AssignmentGroupForm, AssignmentSubmissionForm,
    SubmissionGradeForm, RubricForm, RubricCriterionForm,
    RubricRatingForm, StudentGroupForm, RubricAssessmentForm, QuickGradeForm
)


# ########################################################
# Assignment List & Detail Views
# ########################################################

@login_required
def assignment_list(request, slug):
    """List all assignments for a course"""
    course = get_object_or_404(Course, slug=slug)
    
    # Filter assignments based on user role
    if request.user.is_student:
        assignments = Assignment.objects.filter(
            course=course,
            published=True
        ).order_by('due_date')
        
        # Get submission status for each assignment
        student = get_object_or_404(Student, student=request.user)
        for assignment in assignments:
            submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            assignment.user_submission = submission
    else:
        assignments = Assignment.objects.filter(
            course=course
        ).order_by('due_date')
        
        # Add submission stats for lecturers
        for assignment in assignments:
            assignment.submission_count = assignment.get_submission_count()
            assignment.graded_count = assignment.get_graded_count()
    
    # Group by assignment group
    groups = AssignmentGroup.objects.filter(course=course).order_by('position')
    ungrouped = assignments.filter(group__isnull=True)
    
    context = {
        'title': f'Assignments - {course.title}',
        'course': course,
        'assignments': assignments,
        'groups': groups,
        'ungrouped': ungrouped,
    }
    return render(request, 'assignment/assignment_list.html', context)


@login_required
def assignment_detail(request, slug, assignment_id):
    """View assignment details and submit"""
    course = get_object_or_404(Course, slug=slug)
    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)
    
    submission = None
    form = None
    
    if request.user.is_student:
        student = get_object_or_404(Student, student=request.user)
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student
        ).order_by('-attempt_number').first()
        
        # Check if student can submit
        can_submit = assignment.is_available
        if submission and assignment.allowed_attempts > 0:
            can_submit = submission.attempt_number < assignment.allowed_attempts
        
        if can_submit and request.method == 'POST':
            form = AssignmentSubmissionForm(
                request.POST,
                request.FILES,
                assignment=assignment
            )
            if form.is_valid():
                new_submission = form.save(commit=False)
                new_submission.assignment = assignment
                new_submission.student = student
                new_submission.attempt_number = (submission.attempt_number + 1) if submission else 1
                new_submission.submit()
                messages.success(request, 'Assignment submitted successfully!')
                return redirect('assignment:assignment_detail', slug=slug, assignment_id=assignment_id)
        else:
            form = AssignmentSubmissionForm(assignment=assignment)
    
    # Get rubric if available
    rubric = None
    if assignment.rubric and (assignment.show_rubric_to_students or not request.user.is_student):
        rubric = assignment.rubric
    
    context = {
        'title': assignment.title,
        'course': course,
        'assignment': assignment,
        'submission': submission,
        'form': form,
        'rubric': rubric,
    }
    return render(request, 'assignment/assignment_detail.html', context)


# ########################################################
# Assignment CRUD Views (Lecturer)
# ########################################################

@login_required
@lecturer_required
def assignment_create(request, slug):
    """Create a new assignment"""
    course = get_object_or_404(Course, slug=slug)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, course=course)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            assignment.created_by = request.user
            assignment.save()
            messages.success(request, 'Assignment created successfully!')
            return redirect('assignment:assignment_list', slug=slug)
    else:
        form = AssignmentForm(course=course)
    
    context = {
        'title': 'Create Assignment',
        'course': course,
        'form': form,
    }
    return render(request, 'assignment/assignment_form.html', context)


@login_required
@lecturer_required
def assignment_edit(request, slug, assignment_id):
    """Edit an existing assignment"""
    course = get_object_or_404(Course, slug=slug)
    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment, course=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Assignment updated successfully!')
            return redirect('assignment:assignment_detail', slug=slug, assignment_id=assignment_id)
    else:
        form = AssignmentForm(instance=assignment, course=course)
    
    context = {
        'title': f'Edit: {assignment.title}',
        'course': course,
        'assignment': assignment,
        'form': form,
    }
    return render(request, 'assignment/assignment_form.html', context)


@login_required
@lecturer_required
def assignment_delete(request, slug, assignment_id):
    """Delete an assignment"""
    assignment = get_object_or_404(Assignment, id=assignment_id, course__slug=slug)
    assignment.delete()
    messages.success(request, 'Assignment deleted successfully!')
    return redirect('assignment:assignment_list', slug=slug)


# ########################################################
# Assignment Group Views
# ########################################################

@login_required
@lecturer_required
def assignment_groups(request, slug):
    """Manage assignment groups for weighted grading"""
    course = get_object_or_404(Course, slug=slug)
    groups = AssignmentGroup.objects.filter(course=course).order_by('position')
    
    # Calculate total weight
    total_weight = sum(g.weight for g in groups)
    
    if request.method == 'POST':
        form = AssignmentGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.course = course
            group.save()
            messages.success(request, f'Assignment group "{group.name}" created!')
            return redirect('assignment:assignment_groups', slug=slug)
    else:
        form = AssignmentGroupForm()
    
    context = {
        'title': 'Assignment Groups',
        'course': course,
        'groups': groups,
        'total_weight': total_weight,
        'form': form,
    }
    return render(request, 'assignment/assignment_groups.html', context)


@login_required
@lecturer_required
def assignment_group_edit(request, slug, group_id):
    """Edit assignment group"""
    course = get_object_or_404(Course, slug=slug)
    group = get_object_or_404(AssignmentGroup, id=group_id, course=course)
    
    if request.method == 'POST':
        form = AssignmentGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, 'Assignment group updated!')
            return redirect('assignment:assignment_groups', slug=slug)
    else:
        form = AssignmentGroupForm(instance=group)
    
    context = {
        'title': f'Edit: {group.name}',
        'course': course,
        'group': group,
        'form': form,
    }
    return render(request, 'assignment/assignment_group_form.html', context)


@login_required
@lecturer_required
def assignment_group_delete(request, slug, group_id):
    """Delete assignment group"""
    group = get_object_or_404(AssignmentGroup, id=group_id, course__slug=slug)
    group.delete()
    messages.success(request, 'Assignment group deleted!')
    return redirect('assignment:assignment_groups', slug=slug)


@login_required
@lecturer_required
def assignment_group_create(request, slug):
    """Create a new assignment group"""
    course = get_object_or_404(Course, slug=slug)
    
    if request.method == 'POST':
        form = AssignmentGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.course = course
            group.save()
            messages.success(request, f'Assignment group "{group.name}" created!')
            return redirect('assignment:assignment_groups', slug=slug)
    else:
        form = AssignmentGroupForm()
    
    context = {
        'title': 'New Assignment Group',
        'course': course,
        'form': form,
    }
    return render(request, 'assignment/assignment_group_form.html', context)


# ########################################################
# Student Group Views (for Group Assignments)
# ########################################################

@login_required
@lecturer_required
def student_groups(request, slug):
    """Manage student groups for group assignments"""
    course = get_object_or_404(Course, slug=slug)
    groups = StudentGroup.objects.filter(course=course)
    
    # Get enrolled students
    from result.models import TakenCourse
    enrolled_students = Student.objects.filter(
        taken_courses__course=course
    ).distinct()
    
    if request.method == 'POST':
        form = StudentGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.course = course
            group.save()
            form.save_m2m()  # Save ManyToMany
            messages.success(request, f'Student group "{group.name}" created!')
            return redirect('assignment:student_groups', slug=slug)
    else:
        form = StudentGroupForm()
        form.fields['members'].queryset = enrolled_students
    
    context = {
        'title': 'Student Groups',
        'course': course,
        'groups': groups,
        'form': form,
        'enrolled_students': enrolled_students,
    }
    return render(request, 'assignment/student_groups.html', context)


@login_required
@lecturer_required
def student_group_edit(request, slug, group_id):
    """Edit student group"""
    course = get_object_or_404(Course, slug=slug)
    group = get_object_or_404(StudentGroup, id=group_id, course=course)
    
    from result.models import TakenCourse
    enrolled_students = Student.objects.filter(
        taken_courses__course=course
    ).distinct()
    
    if request.method == 'POST':
        form = StudentGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student group updated!')
            return redirect('assignment:student_groups', slug=slug)
    else:
        form = StudentGroupForm(instance=group)
    form.fields['members'].queryset = enrolled_students
    
    context = {
        'title': f'Edit: {group.name}',
        'course': course,
        'group': group,
        'form': form,
    }
    return render(request, 'assignment/student_group_form.html', context)


@login_required
@lecturer_required
def student_group_delete(request, slug, group_id):
    """Delete student group"""
    group = get_object_or_404(StudentGroup, id=group_id, course__slug=slug)
    group.delete()
    messages.success(request, 'Student group deleted!')
    return redirect('assignment:student_groups', slug=slug)


@login_required
@lecturer_required
def student_group_create(request, slug):
    """Create a new student group"""
    course = get_object_or_404(Course, slug=slug)
    
    from result.models import TakenCourse
    students = Student.objects.filter(
        taken_courses__course=course
    ).distinct()
    
    if request.method == 'POST':
        form = StudentGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.course = course
            group.save()
            form.save_m2m()
            messages.success(request, f'Student group "{group.name}" created!')
            return redirect('assignment:student_groups', slug=slug)
    else:
        form = StudentGroupForm()
    form.fields['members'].queryset = students
    
    context = {
        'title': 'New Student Group',
        'course': course,
        'form': form,
        'students': students,
    }
    return render(request, 'assignment/student_group_form.html', context)


# ########################################################
# Rubric Views
# ########################################################

@login_required
@lecturer_required
def rubric_list(request, slug):
    """List rubrics for a course"""
    course = get_object_or_404(Course, slug=slug)
    rubrics = Rubric.objects.filter(
        Q(course=course) | Q(course__isnull=True)
    ).order_by('-created_at')
    
    context = {
        'title': 'Rubrics',
        'course': course,
        'rubrics': rubrics,
    }
    return render(request, 'assignment/rubric_list.html', context)


@login_required
@lecturer_required
def rubric_create(request, slug):
    """Create a new rubric"""
    course = get_object_or_404(Course, slug=slug)
    
    if request.method == 'POST':
        form = RubricForm(request.POST)
        if form.is_valid():
            rubric = form.save(commit=False)
            rubric.course = course
            rubric.created_by = request.user
            rubric.save()
            messages.success(request, 'Rubric created! Now add criteria.')
            return redirect('assignment:rubric_edit', slug=slug, rubric_id=rubric.id)
    else:
        form = RubricForm()
    
    context = {
        'title': 'Create Rubric',
        'course': course,
        'form': form,
    }
    return render(request, 'assignment/rubric_form.html', context)


@login_required
@lecturer_required
def rubric_edit(request, slug, rubric_id):
    """Edit rubric with criteria and ratings"""
    course = get_object_or_404(Course, slug=slug)
    rubric = get_object_or_404(Rubric, id=rubric_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_rubric':
            form = RubricForm(request.POST, instance=rubric)
            if form.is_valid():
                form.save()
                messages.success(request, 'Rubric updated!')
        
        elif action == 'add_criterion':
            criterion_form = RubricCriterionForm(request.POST)
            if criterion_form.is_valid():
                criterion = criterion_form.save(commit=False)
                criterion.rubric = rubric
                criterion.save()
                messages.success(request, 'Criterion added!')
        
        elif action == 'add_rating':
            criterion_id = request.POST.get('criterion_id')
            criterion = get_object_or_404(RubricCriterion, id=criterion_id)
            rating_form = RubricRatingForm(request.POST)
            if rating_form.is_valid():
                rating = rating_form.save(commit=False)
                rating.criterion = criterion
                rating.save()
                messages.success(request, 'Rating level added!')
        
        return redirect('assignment:rubric_edit', slug=slug, rubric_id=rubric_id)
    
    context = {
        'title': f'Edit Rubric: {rubric.title}',
        'course': course,
        'rubric': rubric,
        'rubric_form': RubricForm(instance=rubric),
        'criterion_form': RubricCriterionForm(),
        'rating_form': RubricRatingForm(),
    }
    return render(request, 'assignment/rubric_edit.html', context)


@login_required
@lecturer_required
def rubric_delete(request, slug, rubric_id):
    """Delete a rubric"""
    rubric = get_object_or_404(Rubric, id=rubric_id)
    rubric.delete()
    messages.success(request, 'Rubric deleted!')
    return redirect('assignment:rubric_list', slug=slug)


@login_required
@lecturer_required
def rubric_criterion_delete(request, slug, criterion_id):
    """Delete a rubric criterion"""
    criterion = get_object_or_404(RubricCriterion, id=criterion_id)
    rubric_id = criterion.rubric.id
    criterion.delete()
    messages.success(request, 'Criterion deleted!')
    return redirect('assignment:rubric_edit', slug=slug, rubric_id=rubric_id)


@login_required
@lecturer_required
def rubric_rating_delete(request, slug, rating_id):
    """Delete a rubric rating"""
    rating = get_object_or_404(RubricRating, id=rating_id)
    rubric_id = rating.criterion.rubric.id
    rating.delete()
    messages.success(request, 'Rating level deleted!')
    return redirect('assignment:rubric_edit', slug=slug, rubric_id=rubric_id)


# ########################################################
# SpeedGrader View
# ########################################################

@login_required
@lecturer_required
def speedgrader(request, slug, assignment_id):
    """Canvas-style SpeedGrader for efficient grading"""
    course = get_object_or_404(Course, slug=slug)
    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)
    
    # Get all submissions
    submissions = AssignmentSubmission.objects.filter(
        assignment=assignment
    ).select_related('student__student').order_by('student__student__last_name')
    
    # Get current submission index
    current_index = int(request.GET.get('index', 0))
    if current_index >= len(submissions):
        current_index = 0
    
    current_submission = submissions[current_index] if submissions else None
    
    # Handle grading
    if request.method == 'POST' and current_submission:
        action = request.POST.get('action')
        
        if action == 'grade':
            form = SubmissionGradeForm(request.POST, assignment=assignment)
            if form.is_valid():
                current_submission.score = form.cleaned_data['score']
                current_submission.feedback = form.cleaned_data['feedback']
                current_submission.graded_by = request.user
                current_submission.graded_at = timezone.now()
                current_submission.status = AssignmentSubmission.STATUS_GRADED
                current_submission.save()
                messages.success(request, 'Grade saved!')
                
                # Move to next ungraded
                next_index = current_index + 1
                if next_index < len(submissions):
                    return redirect(f'{request.path}?index={next_index}')
        
        elif action == 'rubric_grade' and assignment.rubric:
            rubric_form = RubricAssessmentForm(
                request.POST,
                rubric=assignment.rubric,
                submission=current_submission
            )
            
            total_score = Decimal('0')
            for criterion in assignment.rubric.criteria.all():
                rating_id = request.POST.get(f'criterion_{criterion.id}_rating')
                points = request.POST.get(f'criterion_{criterion.id}_points')
                comments = request.POST.get(f'criterion_{criterion.id}_comments', '')
                
                assessment, _ = RubricAssessment.objects.get_or_create(
                    submission=current_submission,
                    criterion=criterion
                )
                
                if rating_id:
                    rating = RubricRating.objects.get(id=rating_id)
                    assessment.rating = rating
                    assessment.points_awarded = rating.points
                elif points:
                    assessment.rating = None
                    assessment.points_awarded = Decimal(points)
                else:
                    assessment.points_awarded = Decimal('0')
                
                assessment.comments = comments
                assessment.save()
                total_score += assessment.points_awarded
            
            # Update submission score
            current_submission.score = total_score
            current_submission.graded_by = request.user
            current_submission.graded_at = timezone.now()
            current_submission.status = AssignmentSubmission.STATUS_GRADED
            current_submission.save()
            messages.success(request, 'Rubric assessment saved!')
    
    # Prepare forms
    grade_form = SubmissionGradeForm(assignment=assignment)
    rubric_form = None
    if assignment.rubric:
        rubric_form = RubricAssessmentForm(
            rubric=assignment.rubric,
            submission=current_submission
        )
    
    # Get quiz sitting data if this is a quiz-type assignment or linked to a quiz
    quiz_sitting = None
    quiz_questions = []
    quiz_incorrect_ids = []
    
    if current_submission:
        from quiz.models import Sitting, Quiz
        try:
            # If assignment is linked to a specific quiz, get that quiz's sitting
            if assignment.linked_quiz:
                quiz_sitting = Sitting.objects.filter(
                    user=current_submission.student.student,
                    quiz=assignment.linked_quiz,
                    complete=True
                ).order_by('-end').first()
            # Otherwise, if it's a quiz-type assignment, find any completed quiz
            elif assignment.assignment_type == Assignment.TYPE_QUIZ:
                quiz_sitting = Sitting.objects.filter(
                    user=current_submission.student.student,
                    quiz__course=course,
                    complete=True
                ).order_by('-end').first()
            
            if quiz_sitting:
                quiz_questions = quiz_sitting.questions_with_user_answers
                quiz_incorrect_ids = list(quiz_sitting.get_incorrect_questions)
        except Exception as e:
            pass  # Quiz data not available
    
    context = {
        'title': f'SpeedGrader: {assignment.title}',
        'course': course,
        'assignment': assignment,
        'submissions': submissions,
        'current_submission': current_submission,
        'current_index': current_index,
        'total_submissions': len(submissions),
        'grade_form': grade_form,
        'rubric_form': rubric_form,
        'prev_index': max(0, current_index - 1),
        'next_index': min(len(submissions) - 1, current_index + 1) if submissions else 0,
        'quiz_sitting': quiz_sitting,
        'quiz_questions': quiz_questions,
        'quiz_incorrect_ids': quiz_incorrect_ids,
    }
    return render(request, 'assignment/speedgrader.html', context)


# ########################################################
# Submission Download
# ########################################################

@login_required
@lecturer_required
def submission_download(request, submission_id):
    """Download a submission file"""
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    if not submission.file_upload:
        raise Http404("No file attached")
    return FileResponse(
        submission.file_upload,
        as_attachment=True,
        filename=submission.original_filename or 'submission'
    )


# ########################################################
# Grade Overview Views
# ########################################################

@login_required
@lecturer_required
def grade_overview(request, slug):
    """Overview of all grades for a course (Gradebook)"""
    course = get_object_or_404(Course, slug=slug)
    
    # Get assignment groups with their assignments
    assignment_groups = AssignmentGroup.objects.filter(course=course).prefetch_related('assignments').order_by('position')
    
    # Get all assignments ordered by group and due date
    assignments = Assignment.objects.filter(course=course).order_by('group__position', 'due_date')
    
    # Get all enrolled students
    from result.models import TakenCourse
    students = Student.objects.filter(
        taken_courses__course=course
    ).distinct().order_by('student__last_name').select_related('student')
    
    # Build grade matrix
    grade_data = []
    total_class_percentage = Decimal('0')
    ungraded_count = 0
    
    for student in students:
        calculator = CourseGradeCalculator(course, student)
        total_percentage = calculator.calculate_weighted_grade() or Decimal('0')
        
        student_data = {
            'student': student,
            'scores': [],
            'total_percentage': total_percentage,
            'letter_grade': calculator.get_letter_grade(),
        }
        
        for assignment in assignments:
            submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            
            score_data = {
                'assignment_id': assignment.id,
                'submission': submission,
                'score': None,
                'percentage': 0,
                'late': False,
            }
            
            if submission:
                if submission.score is not None:
                    score_data['score'] = submission.final_score
                    score_data['percentage'] = (submission.final_score / assignment.points_possible * 100) if assignment.points_possible > 0 else 0
                    score_data['late'] = submission.late_penalty_applied > 0
                else:
                    ungraded_count += 1
            
            student_data['scores'].append(score_data)
        
        grade_data.append(student_data)
        total_class_percentage += total_percentage
    
    # Calculate class average
    class_average = (total_class_percentage / len(students)) if students else Decimal('0')
    
    # Calculate per-assignment averages
    assignment_averages = []
    for assignment in assignments:
        scores = AssignmentSubmission.objects.filter(
            assignment=assignment,
            score__isnull=False
        ).values_list('score', flat=True)
        avg = sum(scores) / len(scores) if scores else 0
        assignment_averages.append(avg)
    
    context = {
        'title': f'Gradebook - {course.title}',
        'course': course,
        'assignment_groups': assignment_groups,
        'assignments': assignments,
        'students': students,
        'grade_data': grade_data,
        'class_average': class_average,
        'assignment_averages': assignment_averages,
        'ungraded_count': ungraded_count,
    }
    return render(request, 'assignment/grade_overview.html', context)


@login_required
def student_grades(request, slug):
    """Student view of their own grades"""
    course = get_object_or_404(Course, slug=slug)
    
    if not request.user.is_student:
        return redirect('assignment:grade_overview', slug=slug)
    
    student = get_object_or_404(Student, student=request.user)
    calculator = CourseGradeCalculator(course, student)
    
    # Get assignment groups with their assignments
    assignment_groups = AssignmentGroup.objects.filter(course=course).prefetch_related('assignments')
    
    # Get grade breakdown by group
    group_grades = []
    points_earned = Decimal('0')
    points_possible = Decimal('0')
    completed_count = 0
    pending_count = 0
    
    for group in assignment_groups:
        group_earned = Decimal('0')
        group_possible = Decimal('0')
        
        for assignment in group.assignments.filter(published=True):
            points_possible += assignment.points_possible
            group_possible += assignment.points_possible
            
            submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            
            # Attach submission to assignment for template
            assignment.user_submission = submission
            
            if submission and submission.score is not None:
                points_earned += submission.final_score
                group_earned += submission.final_score
                completed_count += 1
            elif submission:
                pending_count += 1
            else:
                pending_count += 1
        
        group_percentage = (group_earned / group_possible * 100) if group_possible > 0 else 0
        group_grades.append({
            'name': group.name,
            'weight': group.weight,
            'earned': group_earned,
            'possible': group_possible,
            'percentage': group_percentage,
        })
    
    total_percentage = calculator.calculate_weighted_grade() or Decimal('0')
    letter_grade = calculator.get_letter_grade()
    
    context = {
        'title': f'My Grades - {course.title}',
        'course': course,
        'student': student,
        'assignment_groups': assignment_groups,
        'group_grades': group_grades,
        'total_percentage': total_percentage,
        'letter_grade': letter_grade,
        'points_earned': points_earned,
        'points_possible': points_possible,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'now': timezone.now(),
    }
    return render(request, 'assignment/student_grades.html', context)


# ########################################################
# API Endpoints for AJAX
# ########################################################

@login_required
@lecturer_required
def api_quick_grade(request):
    """AJAX endpoint for quick grade updates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    submission_id = request.POST.get('submission_id')
    score = request.POST.get('score')
    feedback = request.POST.get('feedback', '')
    
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        submission.score = Decimal(score) if score else None
        submission.feedback = feedback
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.status = AssignmentSubmission.STATUS_GRADED
        submission.save()
        
        return JsonResponse({
            'success': True,
            'score': str(submission.score),
            'final_score': str(submission.final_score),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@lecturer_required
def api_publish_assignment(request, assignment_id):
    """AJAX endpoint to toggle assignment publish status"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        assignment.published = not assignment.published
        assignment.save()
        return JsonResponse({
            'success': True,
            'published': assignment.published
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@lecturer_required
def export_grades(request, slug):
    """Export grades to CSV or Excel"""
    import csv
    from django.http import HttpResponse
    
    course = get_object_or_404(Course, slug=slug)
    export_format = request.GET.get('format', 'csv')
    
    # Get all assignments
    assignments = Assignment.objects.filter(course=course).order_by('due_date')
    
    # Get all students enrolled
    from result.models import TakenCourse
    students = Student.objects.filter(
        taken_courses__course=course
    ).distinct().select_related('student')
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{course.slug}_grades.csv"'
        
        writer = csv.writer(response)
        
        # Header row
        headers = ['Student Name', 'Email']
        for assignment in assignments:
            headers.append(f'{assignment.title} ({assignment.points_possible})')
        headers.append('Total %')
        writer.writerow(headers)
        
        # Data rows
        for student in students:
            row = [student.student.get_full_name(), student.student.email]
            calculator = CourseGradeCalculator(course, student)
            
            for assignment in assignments:
                submission = AssignmentSubmission.objects.filter(
                    assignment=assignment,
                    student=student
                ).first()
                
                if submission and submission.score is not None:
                    row.append(str(submission.final_score))
                else:
                    row.append('-')
            
            total = calculator.calculate_weighted_grade()
            row.append(f'{total:.1f}' if total else '-')
            writer.writerow(row)
        
        return response
    
    # Default to CSV
    return redirect('assignment:grade_overview', slug=slug)


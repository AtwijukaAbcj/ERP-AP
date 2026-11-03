from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import CreateView
from django_filters.views import FilterView

from accounts.decorators import (
    course_catalog_access_required,
    lecturer_required,
    student_required,
)
from accounts.models import Student
from core.models import Semester, SiteSettings
from core.pdf_utils import pdf_link_callback
from course.filters import CourseAllocationFilter, ProgramFilter
from course.forms import (
    CourseAddForm,
    CourseAllocationForm,
    EditCourseAllocationForm,
    ProgramForm,
    UploadFormFile,
    UploadFormVideo,
)
from course.models import (
    Course,
    CourseAllocation,
    CourseOffer,
    Program,
    Upload,
    UploadVideo,
)
from result.models import TakenCourse
from .forms import FacultyForm
from accounts.decorators import admin_required 
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Faculty
# ########################################################
# Program Views
# ########################################################
from .models import Faculty


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Sum
from course.models import Program, Course
from course.forms import ProgramForm
from accounts.decorators import faculty_admin_required
from course.forms import CourseAddForm as CourseAddForm

@login_required
@faculty_admin_required
def faculty_program_list(request):
    programs = Program.objects.filter(faculty=request.user.faculty)
    return render(request, "faculty_admin/program_list.html", {
        "programs": programs,
        "title": "My Faculty Programs"
    })

@login_required
@faculty_admin_required
def faculty_program_detail(request, pk):
    program = get_object_or_404(Program, pk=pk, faculty=request.user.faculty)
    courses = Course.objects.filter(program=program).order_by("-year")
    credits = courses.aggregate(total_credits=Sum("credit"))
    return render(request, "faculty_admin/program_single.html", {
        "title": program.title,
        "program": program,
        "courses": courses,
        "credits": credits,
    })

@login_required
@faculty_admin_required
def faculty_add_program(request):
    if request.method == "POST":
        form = ProgramForm(request.POST)
        if form.is_valid():
            program = form.save(commit=False)
            program.faculty = request.user.faculty  # Automatically assign faculty
            program.save()
            messages.success(request, f"{program.title} program has been created.")
            return redirect("faculty_program_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProgramForm()
    return render(request, "faculty_admin/program_add.html", {
        "title": "Add Program",
        "form": form
    })

@login_required
@faculty_admin_required
def faculty_edit_program(request, pk):
    program = get_object_or_404(Program, pk=pk, faculty=request.user.faculty)
    if request.method == "POST":
        form = ProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, f"{program.title} program has been updated.")
            return redirect("faculty_program_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProgramForm(instance=program)
    return render(request, "faculty_admin/program_add.html", {
        "title": "Edit Program",
        "form": form
    })

@login_required
@faculty_admin_required
def faculty_delete_program(request, pk):
    program = get_object_or_404(Program, pk=pk, faculty=request.user.faculty)
    program.delete()
    messages.success(request, "Program deleted successfully.")
    return redirect("faculty_program_list")


@method_decorator([login_required, course_catalog_access_required], name="dispatch")
class ProgramFilterView(FilterView):
    filterset_class = ProgramFilter
    template_name = "course/program_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Programs"
        return context


@login_required
@lecturer_required
def program_add(request):
    if request.method == "POST":
        form = ProgramForm(request.POST)
        if form.is_valid():
            program = form.save()
            messages.success(request, f"{program.title} program has been created.")
            return redirect("programs")
        messages.error(request, "Correct the error(s) below.")
    else:
        form = ProgramForm()
    return render(
        request, "course/program_add.html", {"title": "Add Program", "form": form}
    )


@login_required
def program_detail(request, pk):
    program = get_object_or_404(Program, pk=pk)
    courses = Course.objects.filter(program_id=pk).order_by("-year")
    credits = courses.aggregate(total_credits=Sum("credit"))
    paginator = Paginator(courses, 10)
    page = request.GET.get("page")
    courses = paginator.get_page(page)
    return render(
        request,
        "course/program_single.html",
        {
            "title": program.title,
            "program": program,
            "courses": courses,
            "credits": credits,
        },
    )


@login_required
@lecturer_required
def program_edit(request, pk):
    program = get_object_or_404(Program, pk=pk)
    if request.method == "POST":
        form = ProgramForm(request.POST, instance=program)
        if form.is_valid():
            program = form.save()
            messages.success(request, f"{program.title} program has been updated.")
            return redirect("programs")
        messages.error(request, "Correct the error(s) below.")
    else:
        form = ProgramForm(instance=program)
    return render(
        request, "course/program_add.html", {"title": "Edit Program", "form": form}
    )


@login_required
@lecturer_required
def program_delete(request, pk):
    program = get_object_or_404(Program, pk=pk)
    title = program.title
    program.delete()
    messages.success(request, f"Program {title} has been deleted.")
    return redirect("programs")


# ########################################################
# Course Views
# ########################################################


@login_required
def course_single(request, slug):
    course = get_object_or_404(Course, slug=slug)
    files = Upload.objects.filter(course__slug=slug)
    videos = UploadVideo.objects.filter(course__slug=slug)
    lecturers = CourseAllocation.objects.filter(courses__pk=course.id)
    return render(
        request,
        "course/course_single.html",
        {
            "title": course.title,
            "course": course,
            "files": files,
            "videos": videos,
            "lecturers": lecturers,
            "media_url": settings.MEDIA_URL,
        },
    )


@login_required
@lecturer_required
def course_add(request, pk):
    program = get_object_or_404(Program, pk=pk)
    if request.method == "POST":
        form = CourseAddForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(
                request, f"{course.title} ({course.code}) has been created."
            )
            return redirect("program_detail", pk=program.pk)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = CourseAddForm(initial={"program": program})
    return render(
        request,
        "course/course_add.html",
        {"title": "Add Course", "form": form, "program": program},
    )


@login_required
@lecturer_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if request.method == "POST":
        form = CourseAddForm(request.POST, instance=course)
        if form.is_valid():
            course = form.save()
            messages.success(
                request, f"{course.title} ({course.code}) has been updated."
            )
            return redirect("program_detail", pk=course.program.pk)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = CourseAddForm(instance=course)
    return render(
        request, "course/course_add.html", {"title": "Edit Course", "form": form}
    )


@login_required
@lecturer_required
def course_delete(request, slug):
    course = get_object_or_404(Course, slug=slug)
    title = course.title
    program_id = course.program.id
    course.delete()
    messages.success(request, f"Course {title} has been deleted.")
    return redirect("program_detail", pk=program_id)


# ########################################################
# Course Allocation Views
# ########################################################


@method_decorator([login_required, lecturer_required], name="dispatch")
class CourseAllocationFormView(CreateView):
    form_class = CourseAllocationForm
    template_name = "course/course_allocation_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # ✅ Pass the current user into the form
        return kwargs

    def form_valid(self, form):
        lecturer = form.cleaned_data["lecturer"]
        selected_courses = form.cleaned_data["courses"]
        allocation, created = CourseAllocation.objects.get_or_create(lecturer=lecturer)
        allocation.courses.set(selected_courses)
        messages.success(
            self.request, f"Courses allocated to {lecturer.get_full_name} successfully."
        )
        return redirect("course_allocation_view")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Assign Course"
        return context



@method_decorator([login_required, lecturer_required], name="dispatch")
class CourseAllocationFilterView(FilterView):
    filterset_class = CourseAllocationFilter
    template_name = "course/course_allocation_view.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Course Allocations"
        return context


@login_required
@lecturer_required
def edit_allocated_course(request, pk):
    allocation = get_object_or_404(CourseAllocation, pk=pk)
    if request.method == "POST":
        form = EditCourseAllocationForm(request.POST, instance=allocation)
        if form.is_valid():
            form.save()
            messages.success(request, "Course allocation has been updated.")
            return redirect("course_allocation_view")
        messages.error(request, "Correct the error(s) below.")
    else:
        form = EditCourseAllocationForm(instance=allocation)
    return render(
        request,
        "course/course_allocation_form.html",
        {"title": "Edit Course Allocation", "form": form},
    )


@login_required
@lecturer_required
def deallocate_course(request, pk):
    allocation = get_object_or_404(CourseAllocation, pk=pk)
    allocation.delete()
    messages.success(request, "Successfully deallocated courses.")
    return redirect("course_allocation_view")


# ########################################################
# File Upload Views
# ########################################################


@login_required
@lecturer_required
def handle_file_upload(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if request.method == "POST":
        form = UploadFormFile(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.course = course
            upload.save()
            messages.success(request, f"{upload.title} has been uploaded.")
            return redirect("course_detail", slug=slug)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = UploadFormFile()
    return render(
        request,
        "upload/upload_file_form.html",
        {"title": "File Upload", "form": form, "course": course},
    )


@login_required
@lecturer_required
def handle_file_edit(request, slug, file_id):
    course = get_object_or_404(Course, slug=slug)
    upload = get_object_or_404(Upload, pk=file_id)
    if request.method == "POST":
        form = UploadFormFile(request.POST, request.FILES, instance=upload)
        if form.is_valid():
            upload = form.save()
            messages.success(request, f"{upload.title} has been updated.")
            return redirect("course_detail", slug=slug)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = UploadFormFile(instance=upload)
    return render(
        request,
        "upload/upload_file_form.html",
        {"title": "Edit File", "form": form, "course": course},
    )


@login_required
@lecturer_required
def handle_file_delete(request, slug, file_id):
    upload = get_object_or_404(Upload, pk=file_id)
    title = upload.title
    upload.delete()
    messages.success(request, f"{title} has been deleted.")
    return redirect("course_detail", slug=slug)


# ########################################################
# Video Upload Views
# ########################################################


@login_required
@lecturer_required
def handle_video_upload(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if request.method == "POST":
        form = UploadFormVideo(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.course = course
            video.save()
            messages.success(request, f"{video.title} has been uploaded.")
            return redirect("course_detail", slug=slug)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = UploadFormVideo()
    return render(
        request,
        "upload/upload_video_form.html",
        {"title": "Video Upload", "form": form, "course": course},
    )


@login_required
def handle_video_single(request, slug, video_slug):
    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(UploadVideo, slug=video_slug)
    return render(
        request,
        "upload/video_single.html",
        {"video": video, "course": course},
    )


@login_required
@lecturer_required
def handle_video_edit(request, slug, video_slug):
    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(UploadVideo, slug=video_slug)
    if request.method == "POST":
        form = UploadFormVideo(request.POST, request.FILES, instance=video)
        if form.is_valid():
            video = form.save()
            messages.success(request, f"{video.title} has been updated.")
            return redirect("course_detail", slug=slug)
        messages.error(request, "Correct the error(s) below.")
    else:
        form = UploadFormVideo(instance=video)
    return render(
        request,
        "upload/upload_video_form.html",
        {"title": "Edit Video", "form": form, "course": course},
    )


@login_required
@lecturer_required
def handle_video_delete(request, slug, video_slug):
    video = get_object_or_404(UploadVideo, slug=video_slug)
    title = video.title
    video.delete()
    messages.success(request, f"{title} has been deleted.")
    return redirect("course_detail", slug=slug)


# ########################################################
# Course Registration Views
# ########################################################


@login_required
@student_required
def course_registration(request):
    student = get_object_or_404(Student, student__pk=request.user.id)
    if student.status != Student.Status.ACTIVE:
        messages.error(request, "Only active students can register for courses.")
        return redirect("course_registration")

    current_semester = Semester.objects.filter(is_current_semester=True).first()
    if not current_semester:
        messages.error(request, "No active semester found.")
        return render(
            request,
            "course/course_registration.html",
            {"student": student, "current_semester": None},
        )

    today = timezone.localdate()
    registration_open = (
        current_semester.registration_open_date is None
        or today >= current_semester.registration_open_date
    ) and (
        current_semester.registration_close_date is None
        or today <= current_semester.registration_close_date
    )
    add_drop_open = (
        current_semester.add_drop_open_date is None
        or today >= current_semester.add_drop_open_date
    ) and (
        current_semester.add_drop_close_date is None
        or today <= current_semester.add_drop_close_date
    )

    if request.method == "POST":
        if not registration_open:
            messages.error(request, "Course registration is closed for this academic period.")
            return redirect("course_registration")
        course_ids = list(dict.fromkeys(request.POST.getlist("course_ids")))
        if not course_ids:
            messages.warning(request, "Select at least one course to register.")
            return redirect("course_registration")
        if any(not course_id.isdecimal() for course_id in course_ids):
            messages.error(request, "The selected course list is invalid.")
            return redirect("course_registration")
        if not student.program_id or not student.level or student.year is None:
            messages.error(
                request,
                "Your programme, level, and year must be set before course registration.",
            )
            return redirect("course_registration")

        eligible_courses = Course.objects.filter(
            id__in=course_ids,
            program_id=student.program_id,
            level=student.level,
            year__lte=student.year,
            semester=current_semester.semester,
        )
        if CourseOffer.objects.filter(semester=current_semester).exists():
            offered_course_ids = CourseOffer.objects.filter(
                semester=current_semester,
                dep_head__department_id=student.program_id,
            ).values_list("courses__id", flat=True)
            eligible_courses = eligible_courses.filter(id__in=offered_course_ids)
        courses = list(eligible_courses)
        if len(courses) != len(course_ids):
            messages.error(
                request,
                "One or more selected courses are not available for your programme, year, and current semester.",
            )
            return redirect("course_registration")

        try:
            with transaction.atomic():
                for course in courses:
                    TakenCourse.objects.create(
                        student=student,
                        course=course,
                        semester=current_semester,
                    )
        except IntegrityError:
            messages.error(
                request,
                "One or more selected courses are already registered. Refresh and try again.",
            )
            return redirect("course_registration")

        messages.success(request, "Courses registered successfully!")
        return redirect("course_registration")

    if not student.program_id or not student.level or student.year is None:
        messages.error(
            request,
            "Your programme, level, and year must be set before course registration.",
        )
        available_courses = Course.objects.none()
    elif not registration_open:
        available_courses = Course.objects.none()
        messages.info(request, "Course registration is outside its scheduled calendar window.")
    else:
        registered_course_ids = TakenCourse.objects.filter(
            student=student,
            semester=current_semester,
        ).values_list("course_id", flat=True)
        available_courses = Course.objects.filter(
            program_id=student.program_id,
            level=student.level,
            year__lte=student.year,
            semester=current_semester.semester,
        ).exclude(id__in=registered_course_ids).order_by("year", "code")
        if CourseOffer.objects.filter(semester=current_semester).exists():
            offered_course_ids = CourseOffer.objects.filter(
                semester=current_semester,
                dep_head__department_id=student.program_id,
            ).values_list("courses__id", flat=True)
            available_courses = available_courses.filter(id__in=offered_course_ids)

    registered_enrollments = (
        TakenCourse.objects.filter(
            student=student,
            semester=current_semester,
            course__program_id=student.program_id,
            course__level=student.level,
            course__semester=current_semester.semester,
        )
        .select_related("course")
        .order_by("course__year", "course__code")
    )
    total_registered_credit = sum(
        enrollment.course.credit for enrollment in registered_enrollments
    )
    total_course_credit = sum(course.credit for course in available_courses)
    context = {
        "is_calender_on": True,
        "current_semester": current_semester,
        "courses": available_courses,
        "registered_enrollments": registered_enrollments,
        "total_course_credit": total_course_credit,
        "total_registered_credit": total_registered_credit,
        "student": student,
        "registration_open": registration_open,
        "add_drop_open": add_drop_open,
        "registration_open_date": current_semester.registration_open_date,
        "registration_close_date": current_semester.registration_close_date,
        "add_drop_open_date": current_semester.add_drop_open_date,
        "add_drop_close_date": current_semester.add_drop_close_date,
    }
    return render(request, "course/course_registration.html", context)


@login_required
@student_required
def course_drop(request):
    if request.method == "POST":
        student = get_object_or_404(Student, student__pk=request.user.id)
        if student.status != Student.Status.ACTIVE:
            messages.error(request, "Only active students can drop courses.")
            return redirect("course_registration")
        enrollment_ids = request.POST.getlist("enrollment_ids")
        if any(not enrollment_id.isdecimal() for enrollment_id in enrollment_ids):
            messages.error(request, "The selected enrollment list is invalid.")
            return redirect("course_registration")
        current_semester = Semester.objects.filter(is_current_semester=True).first()
        if not current_semester:
            messages.error(request, "No active semester found.")
            return redirect("course_registration")
        today = timezone.localdate()
        add_drop_open = (
            current_semester.add_drop_open_date is None
            or today >= current_semester.add_drop_open_date
        ) and (
            current_semester.add_drop_close_date is None
            or today <= current_semester.add_drop_close_date
        )
        if not add_drop_open:
            messages.error(request, "Course add/drop is closed for this academic period.")
            return redirect("course_registration")

        dropped_count = TakenCourse.objects.filter(
            id__in=enrollment_ids,
            student=student,
            semester=current_semester,
            course__semester=current_semester.semester,
        ).update(
            is_dropped=True,
            dropped_at=timezone.now(),
            dropped_by=request.user,
        )
        if dropped_count:
            messages.success(request, f"{dropped_count} course(s) dropped successfully.")
        else:
            messages.warning(request, "No current-semester course enrollments were selected.")
        return redirect("course_registration")

    return redirect("course_registration")


# ########################################################
# User Course List View
# ########################################################


@login_required
def user_course_list(request):
    if request.user.is_lecturer:
        courses = Course.objects.filter(allocated_course__lecturer__pk=request.user.id)
        return render(request, "course/user_course_list.html", {"courses": courses})

    if request.user.is_student:
        student = get_object_or_404(Student, student__pk=request.user.id)
        taken_courses = TakenCourse.objects.filter(student=student)
        courses = Course.objects.filter(program=student.program, level=student.level).order_by("year")
        return render(
            request,
            "course/user_course_list.html",
            {
                "student": student,
                "taken_courses": taken_courses,
                "courses": courses
            },
    )

    # For other users
    return render(request, "course/user_course_list.html")

@login_required
@admin_required
def add_faculty_view(request):
    if request.method == 'POST':
        form = FacultyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty created successfully.')
            return redirect('add_faculty')  # or redirect to a faculty list page
    else:
        form = FacultyForm()
    return render(request, 'course/add_faculty.html', {'form': form, 'title': 'Add Faculty'})

@login_required
def manage_faculties_view(request):
    faculties = Faculty.objects.all()
    return render(request, 'course/manage_faculties.html', {
        'faculties': faculties,
        'title': 'Manage Faculties'
    })

def export_faculties_pdf(request):
    faculties = Faculty.objects.all()
    template_path = 'pdf/faculty_list.html'
    context = {
        'faculties': faculties,
        'site_settings': SiteSettings.get_settings(),
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="faculties.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html,
        dest=response,
        link_callback=pdf_link_callback,
    )
    if pisa_status.err:
        return HttpResponse("PDF generation failed.")
    return response


@login_required
def edit_faculty(request, id):
    faculty = get_object_or_404(Faculty, pk=id)
    if request.method == 'POST':
        form = FacultyForm(request.POST, instance=faculty)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty updated successfully.')
            return redirect('manage_faculties')
    else:
        form = FacultyForm(instance=faculty)
    return render(request, 'course/add_faculty.html', {'form': form, 'title': 'Edit Faculty'})


@login_required
def delete_faculty(request, id):
    faculty = get_object_or_404(Faculty, pk=id)
    faculty.delete()
    messages.success(request, 'Faculty deleted successfully.')
    return redirect('manage_faculties')

@login_required
@student_required
def course_registration_form_view(request):
    student = get_object_or_404(Student, student__pk=request.user.id)
    taken_courses = TakenCourse.objects.filter(student=student)
    total_credit = sum(course.course.credit for course in taken_courses)

    return render(request, "course/course_registration_form.html", {
        "student": student,
        "taken_courses": taken_courses,
        "total_credit": total_credit
    })

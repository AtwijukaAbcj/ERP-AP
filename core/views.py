from datetime import date, datetime, time
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db import models
from django.db.models import Case, Count, F, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from audit.models import ActivityLog as AuditActivityLog
from accounts.decorators import (
    admin_required,
    lecturer_required,
    admin_or_faculty_admin_required,
    student_required,
)
from accounts.models import User, Student
from admissions.models import Application, ApplicationStatus
from clinical.models import ClinicalPlacement
from course.models import Course
from finance.models import Invoice, StaffDepartment
from result.models import GRADE_CHOICES, TakenCourse
from .forms import SessionForm, SemesterForm, NewsAndEventsForm
from .models import NewsAndEvents, ActivityLog, Session, Semester
from django.shortcuts import render, get_object_or_404, redirect
from .models import Timetable, TimetableEntry, Room
from .forms import TimetableForm, TimetableEntryForm, RoomForm
from procurement.models import ProcurementPlan
@login_required
@admin_or_faculty_admin_required
def room_list(request):
    rooms = Room.objects.all()
    return render(request, 'core/room_list.html', {'rooms': rooms})


@login_required
@admin_or_faculty_admin_required
def add_room(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Room added successfully.')
            return redirect('room_list')
    else:
        form = RoomForm()
    return render(request, 'core/add_room.html', {'form': form})

# ########################################################
# News & Events
# ########################################################
@login_required
def home_view(request):
    items = NewsAndEvents.objects.all().order_by("-updated_date")
    today = timezone.localdate()
    context = {
        "title": "News & Events",
        "items": items,
        "upcoming_events": NewsAndEvents.objects.filter(
            posted_as="Event",
            event_date__gte=today,
        ).select_related("semester").order_by("event_date", "title"),
        "school_calendar": Semester.objects.select_related("session").order_by(
            "-session__session",
            "semester",
        ),
    }
    return render(request, "core/index.html", context)


def _dashboard_months():
    current_month = timezone.localdate().replace(day=1)
    months = []
    for offset in reversed(range(12)):
        month_number = current_month.year * 12 + current_month.month - 1 - offset
        months.append(date(month_number // 12, month_number % 12 + 1, 1))
    return months


@login_required
@admin_required
def dashboard_view(request):
    online_since = timezone.now() - timedelta(minutes=5)
    online_users = User.objects.filter(
        is_active=True,
        last_activity__gte=online_since,
    ).order_by("-last_activity", "username")
    online_user_count = online_users.count()
    logs = ActivityLog.objects.all().order_by("-created_at")[:10]
    student_count = User.objects.get_student_count()
    lecturer_count = User.objects.get_lecturer_count()
    superuser_count = User.objects.get_superuser_count()
    account_count = User.objects.count()
    course_count = Course.objects.count()
    application_count = Application.objects.count()
    placement_count = ClinicalPlacement.objects.count()
    invoice_count = Invoice.objects.count()
    department_count = StaffDepartment.objects.count()
    procurement_plan_count = ProcurementPlan.objects.filter(
        deleted_at__isnull=True
    ).count()

    application_status_counts = dict(
        Application.objects.values_list("status")
        .annotate(total=Count("pk"))
        .values_list("status", "total")
    )
    enrollment_program_counts = list(
        TakenCourse.objects.values("course__program__title")
        .annotate(total=Count("student_id", distinct=True))
        .order_by("-total", "course__program__title")[:6]
    )
    grade_counts = dict(
        TakenCourse.objects.values_list("grade")
        .annotate(total=Count("pk"))
        .values_list("grade", "total")
    )
    placement_status_counts = dict(
        ClinicalPlacement.objects.values_list("status")
        .annotate(total=Count("pk"))
        .values_list("status", "total")
    )
    invoice_totals = Invoice.objects.aggregate(
        billed=Sum("total_amount"),
        paid=Sum("paid_amount"),
    )
    billed_amount = invoice_totals["billed"] or 0
    paid_amount = invoice_totals["paid"] or 0
    outstanding_amount = billed_amount - paid_amount

    months = _dashboard_months()
    first_month = months[0]
    first_month_start = timezone.make_aware(datetime.combine(first_month, time.min))
    traffic_counts = {
        (row["month"].year, row["month"].month): row
        for row in AuditActivityLog.objects.filter(timestamp__gte=first_month_start)
        .annotate(month=TruncMonth("timestamp"))
        .values("month")
        .annotate(
            actions=Count("pk"),
            users=Count("user_id", distinct=True),
        )
        .order_by("month")
    }
    traffic_by_user_type = list(
        AuditActivityLog.objects.filter(timestamp__gte=first_month_start)
        .annotate(
            user_type=Case(
                When(user__isnull=True, then=Value(_("Anonymous"))),
                When(user__is_superuser=True, then=Value(_("Admin"))),
                When(user__is_student=True, then=Value(_("Student"))),
                When(user__is_lecturer=True, then=Value(_("Lecturer"))),
                When(user__is_dep_head=True, then=Value(_("Department Head"))),
                When(user__is_registrar=True, then=Value(_("Registrar"))),
                When(user__is_finance_manager=True, then=Value(_("Finance Manager"))),
                When(user__is_accountant=True, then=Value(_("Accountant"))),
                When(user__is_finance=True, then=Value(_("Finance Staff"))),
                When(user__is_procurement_manager=True, then=Value(_("Procurement Manager"))),
                When(user__is_procurement_officer=True, then=Value(_("Procurement Officer"))),
                When(user__is_internal_auditor=True, then=Value(_("Internal Auditor"))),
                When(user__is_principal=True, then=Value(_("Principal"))),
                When(user__is_faculty_admin=True, then=Value(_("Faculty Admin"))),
                When(user__is_parent=True, then=Value(_("Parent"))),
                When(user__role__isnull=False, then=F("user__role__name")),
                default=Value(_("User")),
                output_field=models.CharField(),
            )
        )
        .values("user_type")
        .annotate(
            actions=Count("pk"),
            users=Count("user_id", distinct=True),
        )
        .order_by("user_type")
    )
    traffic_trends = [
        {
            "label": date_format(month, "M Y"),
            "actions": traffic_counts.get((month.year, month.month), {}).get("actions", 0),
            "users": traffic_counts.get((month.year, month.month), {}).get("users", 0),
            "x": 30 + round(index * 600 / 11),
        }
        for index, month in enumerate(months)
    ]
    enrollment_periods = list(
        TakenCourse.objects.filter(semester__isnull=False, semester__session__isnull=False)
        .values("semester__session__session", "semester__semester")
        .annotate(total=Count("pk"))
        .order_by("-semester__session__session", "-semester__semester")[:12]
    )
    enrollment_periods.reverse()
    enrollment_trends = [
        {
            "label": f'{row["semester__session__session"] or _("Unassigned session")} · '
            f'{row["semester__semester"]}',
            "value": row["total"],
            "x": (
                330
                if len(enrollment_periods) == 1
                else 30 + round(index * 600 / (len(enrollment_periods) - 1))
            ),
        }
        for index, row in enumerate(enrollment_periods)
    ]
    traffic_max = max(
        (max(row["actions"], row["users"]) for row in traffic_trends),
        default=0,
    )
    enrollment_max = max((row["value"] for row in enrollment_trends), default=0)
    for row in traffic_trends:
        row["actions_y"] = 190 - round(row["actions"] / traffic_max * 155) if traffic_max else 190
        row["users_y"] = 190 - round(row["users"] / traffic_max * 155) if traffic_max else 190
    for row in enrollment_trends:
        row["y"] = 190 - round(row["value"] / enrollment_max * 155) if enrollment_max else 190

    chart_data = {
        "admissions": [
            {
                "label": label,
                "value": application_status_counts.get(status, 0),
            }
            for status, label in ApplicationStatus.objects.filter(
                is_active=True
            ).values_list("code", "name")
        ],
        "enrollments": [
            {
                "label": item["course__program__title"] or _("Unassigned program"),
                "value": item["total"],
            }
            for item in enrollment_program_counts
        ],
        "results": [
            {"label": grade, "value": grade_counts.get(grade, 0)}
            for grade, _label in GRADE_CHOICES
        ],
        "placements": [
            {
                "label": label,
                "value": placement_status_counts.get(status, 0),
            }
            for status, label in ClinicalPlacement.Status.choices
        ],
        "finance": [
            {"label": _("Collected"), "value": paid_amount},
            {"label": _("Outstanding"), "value": outstanding_amount},
        ],
    }
    for chart_rows in chart_data.values():
        chart_max = max((row["value"] for row in chart_rows), default=0)
        for row in chart_rows:
            row["percent"] = round(row["value"] / chart_max * 100) if chart_max else 0

    module_cards = [
        {
            "title": _("Admissions & Applicants"),
            "description": _("Review applications and manage admission decisions."),
            "url": reverse("admissions:dashboard"),
            "icon": "fa-user-check",
            "color": "violet",
            "count": application_count,
            "count_label": _("applications"),
        },
        {
            "title": _("Student Management"),
            "description": _("Open student records, lifecycle status, and documents."),
            "url": reverse("student_list"),
            "icon": "fa-user-graduate",
            "color": "blue",
            "count": student_count,
            "count_label": _("students"),
        },
        {
            "title": _("Academic Management"),
            "description": _("Manage course enrolment, academic sessions, and terms."),
            "url": reverse("course_enrollment"),
            "icon": "fa-book-open",
            "color": "teal",
            "count": course_count,
            "count_label": _("courses"),
        },
        {
            "title": _("Clinical Training"),
            "description": _("Coordinate ward placements, supervision, and logbooks."),
            "url": reverse("clinical:placement_list"),
            "icon": "fa-user-nurse",
            "color": "green",
            "count": placement_count,
            "count_label": _("placements"),
        },
        {
            "title": _("Examinations & Results"),
            "description": _("Open assessment setup, score entry, and student results."),
            "url": reverse("assessment_hub"),
            "icon": "fa-clipboard-check",
            "color": "orange",
        },
        {
            "title": _("Finance & Student Billing"),
            "description": _("Manage invoices, student payments, and finance records."),
            "url": reverse("finance:finance_dashboard"),
            "icon": "fa-coins",
            "color": "amber",
            "count": invoice_count,
            "count_label": _("invoices"),
        },
        {
            "title": _("Procurement"),
            "description": _("Manage procurement plans, requisitions, and orders."),
            "url": reverse("procurement:dashboard"),
            "icon": "fa-cart-shopping",
            "color": "indigo",
            "count": procurement_plan_count,
            "count_label": _("active plans"),
        },
        {
            "title": _("Staff & Departments"),
            "description": _("Manage staff assignments and department records."),
            "url": reverse("finance:staff_department_list"),
            "icon": "fa-people-group",
            "color": "rose",
            "count": department_count,
            "count_label": _("departments"),
        },
        {
            "title": _("Reporting & Analytics"),
            "description": _("Review cross-module institutional reports and exports."),
            "url": reverse("institutional_reports"),
            "icon": "fa-chart-line",
            "color": "cyan",
        },
        {
            "title": _("System Administration & Security"),
            "description": _("Manage accounts, roles, permissions, and audit access."),
            "url": reverse("access_control_home"),
            "icon": "fa-shield-halved",
            "color": "slate",
            "count": account_count,
            "count_label": _("accounts"),
        },
    ]

    context = {
        "student_count": student_count,
        "lecturer_count": lecturer_count,
        "superuser_count": superuser_count,
        "online_users": online_users[:20],
        "online_user_count": online_user_count,
        "course_count": course_count,
        "procurement_plan_count": procurement_plan_count,
        "module_cards": module_cards,
        "dashboard_charts": chart_data,
        "traffic_trends": traffic_trends,
        "traffic_by_user_type": traffic_by_user_type,
        "enrollment_trends": enrollment_trends,
        "logs": logs,
    }
    return render(request, "core/dashboard.html", context)


@login_required
@admin_required
def post_add(request):
    if request.method == "POST":
        form = NewsAndEventsForm(request.POST)
        title = form.cleaned_data.get("title", "Post") if form.is_valid() else None
        if form.is_valid():
            form.save()
            messages.success(request, f"{title} has been uploaded.")
            return redirect("home")
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = NewsAndEventsForm()
    return render(request, "core/post_add.html", {"title": "Add Post", "form": form})


@login_required
@admin_required
def edit_post(request, pk):
    instance = get_object_or_404(NewsAndEvents, pk=pk)
    if request.method == "POST":
        form = NewsAndEventsForm(request.POST, instance=instance)
        title = form.cleaned_data.get("title", "Post") if form.is_valid() else None
        if form.is_valid():
            form.save()
            messages.success(request, f"{title} has been updated.")
            return redirect("home")
        messages.error(request, "Please correct the error(s) below.")
    else:
        form = NewsAndEventsForm(instance=instance)
    return render(request, "core/post_add.html", {"title": "Edit Post", "form": form})


@login_required
@admin_required
def delete_post(request, pk):
    post = get_object_or_404(NewsAndEvents, pk=pk)
    post_title = post.title
    post.delete()
    messages.success(request, f"{post_title} has been deleted.")
    return redirect("home")


# ########################################################
# Session
# ########################################################
@login_required
@lecturer_required
def session_list_view(request):
    """Show list of all sessions"""
    sessions = Session.objects.all().order_by("-is_current_session", "-session")
    return render(request, "core/session_list.html", {"sessions": sessions})


@login_required
@lecturer_required
def session_add_view(request):
    """Add a new session"""
    if request.method == "POST":
        form = SessionForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("is_current_session"):
                unset_current_session()
            form.save()
            messages.success(request, "Session added successfully.")
            return redirect("session_list")
    else:
        form = SessionForm()
    return render(request, "core/session_update.html", {"form": form})


@login_required
@lecturer_required
def session_update_view(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == "POST":
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            if form.cleaned_data.get("is_current_session"):
                unset_current_session()
            form.save()
            messages.success(request, "Session updated successfully.")
            return redirect("session_list")
    else:
        form = SessionForm(instance=session)
    return render(request, "core/session_update.html", {"form": form})


@login_required
@lecturer_required
def session_delete_view(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if session.is_current_session:
        messages.error(request, "You cannot delete the current session.")
    else:
        session.delete()
        messages.success(request, "Session successfully deleted.")
    return redirect("session_list")


def unset_current_session():
    """Unset current session"""
    current_session = Session.objects.filter(is_current_session=True).first()
    if current_session:
        current_session.is_current_session = False
        current_session.save()


def set_current_session(session):
    Session.objects.exclude(pk=session.pk).filter(
        is_current_session=True
    ).update(is_current_session=False)
    Session.objects.filter(pk=session.pk).update(is_current_session=True)


# ########################################################
# Semester
# ########################################################
@login_required
@lecturer_required
def semester_list_view(request):
    semesters = Semester.objects.all().order_by("-is_current_semester", "-semester")
    return render(request, "core/semester_list.html", {"semesters": semesters})


@login_required
@lecturer_required
def semester_add_view(request):
    if request.method == "POST":
        form = SemesterForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("is_current_semester"):
                with transaction.atomic():
                    unset_current_semester()
                    set_current_session(form.cleaned_data["session"])
                    form.save()
            else:
                form.save()
            messages.success(request, "Semester added successfully.")
            return redirect("semester_list")
    else:
        form = SemesterForm()
    return render(request, "core/semester_update.html", {"form": form})


@login_required
@lecturer_required
def semester_update_view(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    if request.method == "POST":
        form = SemesterForm(request.POST, instance=semester)
        if form.is_valid():
            if form.cleaned_data.get("is_current_semester"):
                with transaction.atomic():
                    unset_current_semester()
                    set_current_session(form.cleaned_data["session"])
                    form.save()
            else:
                form.save()
            messages.success(request, "Semester updated successfully!")
            return redirect("semester_list")
    else:
        form = SemesterForm(instance=semester)
    return render(request, "core/semester_update.html", {"form": form})


@login_required
@lecturer_required
def semester_delete_view(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    if semester.is_current_semester:
        messages.error(request, "You cannot delete the current semester.")
    else:
        semester.delete()
        messages.success(request, "Semester successfully deleted.")
    return redirect("semester_list")


def unset_current_semester():
    """Unset current semester"""
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    if current_semester:
        current_semester.is_current_semester = False
        current_semester.save()

@login_required
@admin_or_faculty_admin_required
def timetable_list(request):
    timetables = Timetable.objects.prefetch_related(
        'entries__course', 'entries__lecturer', 'entries__room', 'program'
    ).all()
    return render(request, 'core/timetable_list.html', {'timetables': timetables})

@admin_or_faculty_admin_required
def add_timetable(request):
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            timetable = form.save()
            return redirect('timetable_detail', pk=timetable.pk)
    else:
        form = TimetableForm()
    return render(request, 'core/add_timetable.html', {'form': form})

def generate_time_choices(start, end, step_minutes=30):
    times = []
    current = time(hour=start)
    while current < time(hour=end):
        times.append((current.strftime('%H:%M'), current.strftime('%H:%M')))
        hour = current.hour
        minute = current.minute + step_minutes
        if minute >= 60:
            hour += 1
            minute = minute % 60
        current = time(hour=hour, minute=minute)
    return times

TIME_CHOICES = generate_time_choices(8, 18)

@admin_or_faculty_admin_required
def add_timetable_entry(request, timetable_id):
    timetable = get_object_or_404(Timetable, pk=timetable_id)
    if request.method == 'POST':
        form = TimetableEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.timetable = timetable
            entry.save()
            return redirect('timetable_detail', pk=timetable.id)
    else:
        form = TimetableEntryForm(initial={'timetable': timetable})
    return render(request, 'core/add_timetable_entry.html', {'form': form, 'timetable': timetable})

@admin_or_faculty_admin_required
def edit_timetable(request, pk):
    timetable = get_object_or_404(Timetable, pk=pk)
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=timetable)
        if form.is_valid():
            form.save()
            messages.success(request, "Timetable updated successfully.")
            return redirect('timetable_list')
    else:
        form = TimetableForm(instance=timetable)
    return render(request, 'core/add_timetable.html', {'form': form, 'edit_mode': True})


@login_required
@admin_or_faculty_admin_required
def delete_timetable(request, pk):
    timetable = get_object_or_404(Timetable, pk=pk)
    timetable.delete()
    messages.success(request, "Timetable deleted successfully.")
    return redirect('timetable_list')

@login_required
@admin_or_faculty_admin_required
def timetable_detail(request, pk):
    timetable = get_object_or_404(
        Timetable.objects.prefetch_related(
            'entries__course', 'entries__lecturer', 'entries__room'
        ),
        pk=pk
    )
    return render(request, 'core/timetable_detail.html', {'timetable': timetable})


@login_required
@admin_or_faculty_admin_required
def delete_timetable_entry(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk)
    timetable_id = entry.timetable.id
    entry.delete()
    messages.success(request, "Timetable entry deleted successfully.")
    return redirect('timetable_detail', pk=timetable_id)

@login_required
@student_required
def student_timetable_view(request):
    student = get_object_or_404(Student, student=request.user)
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    timetables = Timetable.objects.none()
    if not current_semester:
        messages.error(request, "No active semester is configured.")
    elif not current_semester.session_id:
        messages.error(request, "The active semester is not linked to an academic session.")
    else:
        timetables = Timetable.objects.filter(
            program=student.program,
            semester=current_semester.semester,
            academic_year=current_semester.session.session,
        ).prefetch_related('entries__course', 'entries__lecturer', 'entries__room')

    return render(request, 'core/student_timetable.html', {
        'timetables': timetables,
        'current_semester': current_semester,
        'student': student,
        'title': 'My Timetable'
    })


# ########################################################
# Site Settings
# ########################################################
@login_required
@admin_required
def site_settings_view(request):
    return render(request, "core/site_settings.html", {
        "title": "Site Settings",
    })


@login_required
@admin_required
def email_settings_view(request):
    from .models import EmailServerSettings
    from .forms import EmailServerSettingsForm

    email_settings = EmailServerSettings.get_settings()
    if request.method == 'POST':
        email_form = EmailServerSettingsForm(request.POST, instance=email_settings)
        if email_form.is_valid():
            email_form.save()
            messages.success(request, "Email server settings updated.")
            return redirect('site_settings_email')
    else:
        email_form = EmailServerSettingsForm(instance=email_settings)

    return render(request, 'core/site_settings_detail.html', {
        'section': 'email',
        'section_title': 'Email Server',
        'email_form': email_form,
        'email_password_configured': bool(email_settings.encrypted_password),
        'title': 'Email Server Settings',
    })


def _site_settings_form_view(request, form_class, section, section_title):
    from .models import SiteSettings

    settings = SiteSettings.get_settings()
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, f"{section_title} settings updated successfully.")
            return redirect(section)
    else:
        form = form_class(instance=settings)

    return render(request, "core/site_settings_detail.html", {
        "section": section.removeprefix("site_settings_"),
        "section_title": section_title,
        "form": form,
        "settings": settings,
        "title": section_title,
    })


@login_required
@admin_required
def branding_settings_view(request):
    from .forms import BrandingSettingsForm

    return _site_settings_form_view(
        request,
        BrandingSettingsForm,
        "site_settings_branding",
        "Branding & Logo",
    )


@login_required
@admin_required
def school_settings_view(request):
    from .forms import SchoolInformationSettingsForm

    return _site_settings_form_view(
        request,
        SchoolInformationSettingsForm,
        "site_settings_school",
        "School Information",
    )


@login_required
@admin_required
def student_identifier_settings_view(request):
    from .forms import StudentIdentifierSettingsForm

    return _site_settings_form_view(
        request,
        StudentIdentifierSettingsForm,
        "site_settings_student_ids",
        "Student Registration Numbers",
    )


# ########################################################
# Course Progress View
# ########################################################
@login_required
def course_progress_view(request):
    """
    Shows course progress based on user role:
    - Students: Their enrolled courses with assessment breakdown and quiz results
    - Lecturers: Progress of students in their assigned courses
    - Admins: Overall system progress overview
    """
    from accounts.models import Student
    from course.models import Course
    from result.models import TakenCourse, Result
    from quiz.models import Quiz, Sitting, Progress
    from .models import Session, Semester
    from django.db.models import Q
    
    user = request.user
    context = {
        'title': 'Course Progress',
    }
    
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    context['current_session'] = current_session
    context['current_semester'] = current_semester
    
    if user.is_student:
        # Student view - show their personal progress
        try:
            student = Student.objects.get(student__pk=user.id)
            context['student'] = student
            
            # Get enrolled courses with grades
            taken_courses = TakenCourse.objects.filter(
                student__student__pk=user.id
            ).select_related('course')
            
            # Calculate progress for each course
            course_progress = []
            for tc in taken_courses:
                # Get quiz attempts for this course
                quiz_attempts = Sitting.objects.filter(
                    user=user,
                    course=tc.course,
                    complete=True
                ).order_by('-end')
                
                # Calculate assessment completion
                assessments = {
                    'assignment': {'score': float(tc.assignment), 'max': 15, 'completed': tc.assignment > 0},
                    'mid_exam': {'score': float(tc.mid_exam), 'max': 15, 'completed': tc.mid_exam > 0},
                    'quiz': {'score': float(tc.quiz), 'max': 15, 'completed': tc.quiz > 0},
                    'attendance': {'score': float(tc.attendance), 'max': 5, 'completed': tc.attendance > 0},
                    'final_exam': {'score': float(tc.final_exam), 'max': 50, 'completed': tc.final_exam > 0},
                }
                
                completed_assessments = sum(1 for a in assessments.values() if a['completed'])
                total_assessments = len(assessments)
                progress_percent = int((completed_assessments / total_assessments) * 100) if total_assessments > 0 else 0
                
                course_progress.append({
                    'course': tc.course,
                    'taken_course': tc,
                    'assessments': assessments,
                    'quiz_attempts': quiz_attempts,
                    'progress_percent': progress_percent,
                    'completed_assessments': completed_assessments,
                    'total_assessments': total_assessments,
                })
            
            context['course_progress'] = course_progress
            
            # Get overall results
            results = Result.objects.filter(student__student__pk=user.id)
            context['results'] = results
            
            # Get all quiz attempts
            all_quiz_attempts = Sitting.objects.filter(user=user, complete=True).order_by('-end')
            context['all_quiz_attempts'] = all_quiz_attempts
            
        except Student.DoesNotExist:
            context['error'] = 'Student profile not found.'
        
        return render(request, 'core/course_progress_student.html', context)
    
    elif user.is_lecturer:
        # Lecturer view - show progress of students in their courses
        courses = Course.objects.filter(
            allocated_course__lecturer__pk=user.id
        )
        
        if current_semester:
            courses = courses.filter(semester=current_semester.semester)
        
        course_data = []
        for course in courses:
            # Get students taking this course
            students_in_course = TakenCourse.objects.filter(course=course)
            if current_semester:
                students_in_course = students_in_course.filter(
                    Q(semester=current_semester) | Q(semester__isnull=True)
                )
            students_in_course = students_in_course.select_related('student__student')
            
            # Calculate statistics
            total_students = students_in_course.count()
            passed = students_in_course.filter(comment='PASS').count()
            failed = students_in_course.filter(comment='FAIL').count()
            pending = total_students - passed - failed
            
            # Get quiz attempts
            quizzes = Quiz.objects.filter(course=course)
            quiz_completion = []
            for quiz in quizzes:
                completed = Sitting.objects.filter(quiz=quiz, complete=True).count()
                quiz_completion.append({
                    'quiz': quiz,
                    'completed': completed,
                    'total_students': total_students,
                    'percent': int((completed / total_students) * 100) if total_students > 0 else 0
                })
            
            # Calculate average score
            avg_total = students_in_course.aggregate(avg=models.Avg('total'))['avg'] or 0
            
            course_data.append({
                'course': course,
                'total_students': total_students,
                'passed': passed,
                'failed': failed,
                'pending': pending,
                'pass_rate': int((passed / total_students) * 100) if total_students > 0 else 0,
                'avg_score': round(avg_total, 1),
                'quizzes': quiz_completion,
                'students': students_in_course[:10],  # Show top 10
            })
        
        context['course_data'] = course_data
        return render(request, 'core/course_progress_lecturer.html', context)
    
    else:
        # Admin view - system overview
        total_students = Student.objects.count()
        total_courses = Course.objects.count()
        
        # Get all taken courses for stats
        all_taken = TakenCourse.objects.all()
        total_enrollments = all_taken.count()
        passed_count = all_taken.filter(comment='PASS').count()
        failed_count = all_taken.filter(comment='FAIL').count()
        
        # Quiz statistics
        total_quizzes = Quiz.objects.count()
        total_quiz_attempts = Sitting.objects.filter(complete=True).count()
        
        # Recent quiz attempts
        recent_attempts = Sitting.objects.filter(complete=True).order_by('-end')[:20]
        
        context.update({
            'total_students': total_students,
            'total_courses': total_courses,
            'total_enrollments': total_enrollments,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'pass_rate': int((passed_count / total_enrollments) * 100) if total_enrollments > 0 else 0,
            'total_quizzes': total_quizzes,
            'total_quiz_attempts': total_quiz_attempts,
            'recent_attempts': recent_attempts,
        })
        
        return render(request, 'core/course_progress_admin.html', context)

# ########################################################
# Assessment Dashboard View
# ########################################################
@login_required
def assessment_dashboard_view(request):
    """
    Comprehensive assessment management dashboard for lecturers and admins.
    Shows all assessments, pending grading, and student results.
    """
    from accounts.models import Student
    from course.models import Course, CourseAllocation
    from result.models import TakenCourse, Result
    from quiz.models import Quiz, Sitting, Progress
    from .models import Session, Semester
    from django.db.models import Count, Avg, Q
    
    user = request.user
    context = {
        'title': 'Assessment Dashboard',
    }
    
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    context['current_session'] = current_session
    context['current_semester'] = current_semester
    
    if user.is_lecturer:
        # Get courses allocated to this lecturer
        allocated_courses = Course.objects.filter(
            allocated_course__lecturer__pk=user.id
        )
        
        if current_semester:
            allocated_courses = allocated_courses.filter(semester=current_semester.semester)
        
        context['allocated_courses'] = allocated_courses
        
        # Get all quizzes for allocated courses grouped by category
        assignments = Quiz.objects.filter(course__in=allocated_courses, category='assignment')
        exams = Quiz.objects.filter(course__in=allocated_courses, category='exam')
        practice_quizzes = Quiz.objects.filter(course__in=allocated_courses, category='practice')
        
        context['assignments'] = assignments
        context['exams'] = exams
        context['practice_quizzes'] = practice_quizzes
        
        # Stats
        context['total_assignments'] = assignments.count()
        context['total_exams'] = exams.count()
        context['total_practice'] = practice_quizzes.count()
        
        # Pending marking (exam_paper quizzes with complete sittings)
        pending_marking = Sitting.objects.filter(
            quiz__course__in=allocated_courses,
            quiz__exam_paper=True,
            complete=True
        ).select_related('user', 'quiz', 'quiz__course')
        context['pending_marking'] = pending_marking
        context['pending_count'] = pending_marking.count()
        
        # Students enrolled in lecturer's courses
        if current_semester:
            enrolled_students = TakenCourse.objects.filter(
                course__in=allocated_courses,
                course__semester=current_semester.semester,
            ).filter(
                Q(semester=current_semester) | Q(semester__isnull=True)
            ).select_related('student', 'course')
        else:
            enrolled_students = TakenCourse.objects.filter(
                course__in=allocated_courses
            ).select_related('student', 'course')
        
        context['enrolled_students'] = enrolled_students
        context['enrolled_count'] = enrolled_students.count()
        
        # Students needing grades (total=0 means not graded)
        ungraded_students = enrolled_students.filter(total=0)
        context['ungraded_count'] = ungraded_students.count()
        
        # Recent quiz attempts
        recent_attempts = Sitting.objects.filter(
            quiz__course__in=allocated_courses,
            complete=True
        ).order_by('-end')[:10]
        context['recent_attempts'] = recent_attempts
        
        # Per-course breakdown
        course_data = []
        for course in allocated_courses:
            course_quizzes = Quiz.objects.filter(course=course)
            course_sittings = Sitting.objects.filter(quiz__course=course, complete=True)
            course_students = TakenCourse.objects.filter(course=course)
            
            if current_semester:
                course_students = course_students.filter(
                    course__semester=current_semester.semester,
                ).filter(
                    Q(semester=current_semester) | Q(semester__isnull=True)
                )
            
            course_data.append({
                'course': course,
                'quiz_count': course_quizzes.count(),
                'assignment_count': course_quizzes.filter(category='assignment').count(),
                'exam_count': course_quizzes.filter(category='exam').count(),
                'attempt_count': course_sittings.count(),
                'student_count': course_students.count(),
                'graded_count': course_students.exclude(total=0).count(),
                'avg_score': course_students.aggregate(avg=Avg('total'))['avg'] or 0,
            })
        context['course_data'] = course_data
        
        return render(request, 'core/assessment_dashboard_lecturer.html', context)
    
    else:
        # Admin view - system-wide assessment overview
        all_quizzes = Quiz.objects.all()
        all_courses = Course.objects.all()
        
        # Assessment counts by category
        context['total_assignments'] = all_quizzes.filter(category='assignment').count()
        context['total_exams'] = all_quizzes.filter(category='exam').count()
        context['total_practice'] = all_quizzes.filter(category='practice').count()
        context['total_quizzes'] = all_quizzes.count()
        
        # Sitting statistics
        all_sittings = Sitting.objects.all()
        context['total_attempts'] = all_sittings.filter(complete=True).count()
        context['pending_marking'] = all_sittings.filter(complete=True, quiz__exam_paper=True).count()
        
        # Grading statistics
        all_taken = TakenCourse.objects.all()
        context['total_enrollments'] = all_taken.count()
        context['graded_count'] = all_taken.exclude(total=0).count()
        context['ungraded_count'] = all_taken.filter(total=0).count()
        
        # Pass/Fail stats
        graded_taken = all_taken.exclude(total=0)
        context['passed_count'] = graded_taken.filter(comment='PASS').count()
        context['failed_count'] = graded_taken.filter(comment='FAIL').count()
        
        # Average scores
        context['avg_score'] = graded_taken.aggregate(avg=Avg('total'))['avg'] or 0
        
        # Recent activity
        context['recent_attempts'] = Sitting.objects.filter(complete=True).order_by('-end')[:15]
        context['recent_grades'] = all_taken.exclude(total=0).order_by('-id')[:15]
        
        # Per-category quiz list
        context['assignments'] = all_quizzes.filter(category='assignment').select_related('course')[:10]
        context['exams'] = all_quizzes.filter(category='exam').select_related('course')[:10]
        context['practice_quizzes'] = all_quizzes.filter(category='practice').select_related('course')[:10]
        
        return render(request, 'core/assessment_dashboard_admin.html', context)


# ########################################################
# Course Enrollment Management
# ########################################################
@login_required
@admin_required
def course_enrollment_view(request):
    """
    Admin view for managing student enrollments in courses.
    Allows enrolling students to courses and viewing/removing enrollments.
    """
    from result.models import TakenCourse
    from course.models import Course
    
    courses = Course.objects.select_related('program').order_by('title')
    students = Student.objects.filter(
        status=Student.Status.ACTIVE,
        student__is_active=True,
    ).select_related('student').order_by('student__first_name', 'student__last_name')
    
    selected_course = None
    enrolled_students = []
    available_students = []
    current_semester = Semester.objects.filter(is_current_semester=True).first()

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id)
        if current_semester:
            enrolled_students = TakenCourse.objects.filter(
                course=selected_course,
                semester=current_semester,
            ).select_related('student__student')
            enrolled_student_ids = enrolled_students.values_list(
                'student_id', flat=True
            )
        else:
            enrolled_student_ids = []
        available_students = students.filter(
            program_id=selected_course.program_id,
            level=selected_course.level,
            year__gte=selected_course.year,
        ).exclude(id__in=enrolled_student_ids)
    
    # Handle POST requests for enrollment actions
    if request.method == 'POST':
        action = request.POST.get('action')
        course_id = request.POST.get('course_id')
        
        if course_id:
            course = get_object_or_404(Course, id=course_id)
            current_semester = Semester.objects.filter(is_current_semester=True).first()
            if not current_semester or course.semester != current_semester.semester:
                messages.error(request, 'Enrollments can only be managed for courses in the active semester.')
                return redirect(f"{request.path}?course={course_id}")
            
            if action == 'enroll':
                student_ids = request.POST.getlist('student_ids')
                enrolled_count = 0
                for student_id in student_ids:
                    student = students.filter(
                        id=student_id,
                        program_id=course.program_id,
                        level=course.level,
                        year__gte=course.year,
                    ).first()
                    if student and not TakenCourse.all_objects.filter(
                        student=student,
                        course=course,
                        semester=current_semester,
                        is_dropped=False,
                    ).exists():
                        TakenCourse.objects.create(
                            student=student,
                            course=course,
                            semester=current_semester,
                        )
                        enrolled_count += 1
                if enrolled_count:
                    messages.success(request, f'Successfully enrolled {enrolled_count} student(s) to {course.title}.')
                else:
                    messages.warning(request, 'No new students were enrolled.')
                    
            elif action == 'unenroll':
                enrollment_ids = request.POST.getlist('enrollment_ids')
                dropped_count = TakenCourse.objects.filter(
                    id__in=enrollment_ids,
                    course=course,
                    semester=current_semester,
                ).update(
                    is_dropped=True,
                    dropped_at=timezone.now(),
                    dropped_by=request.user,
                )
                if dropped_count:
                    messages.success(request, f'Successfully dropped {dropped_count} enrollment(s) from {course.title}.')
                else:
                    messages.warning(request, 'No enrollments were removed.')
            
            return redirect(f"{request.path}?course={course_id}")
    
    context = {
        'title': 'Course Enrollment Management',
        'courses': courses,
        'students': students,
        'selected_course': selected_course,
        'enrolled_students': enrolled_students,
        'available_students': available_students,
    }
    return render(request, 'core/course_enrollment.html', context)
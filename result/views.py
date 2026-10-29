from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT

# from reportlab.platypus.tables import Table
from reportlab.lib.units import inch
from reportlab.lib import colors

from core.models import Session, Semester
from course.models import Course
from accounts.models import Student
from accounts.decorators import lecturer_required, student_required
from .models import TakenCourse, Result
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from accounts.models import Student
from course.models import Course
from core.models import Session, Semester
from result.models import TakenCourse

CM = 2.54


# ########################################################
# Score Add & Add for
# ########################################################
@login_required
@lecturer_required
def add_score(request):
    """
    Shows a page where a lecturer will select a course allocated
    to him for score entry. in a specific semester and session
    """
    current_semester = (
        Semester.objects.filter(is_current_semester=True)
        .select_related("session")
        .first()
    )
    current_session = current_semester.session if current_semester else None

    if not current_semester or not current_session:
        messages.error(request, "No active semester found.")
        return render(request, "result/add_score.html")

    # semester = Course.objects.filter(
    # allocated_course__lecturer__pk=request.user.id,
    # semester=current_semester)
    courses = Course.objects.filter(
        allocated_course__lecturer__pk=request.user.id
    ).filter(semester=current_semester.semester)
    context = {
        "current_session": current_session,
        "current_semester": current_semester,
        "courses": courses,
    }
    return render(request, "result/add_score.html", context)


@login_required
@lecturer_required
def add_score_for(request, id):
    """
    Shows a page where a lecturer will add score for students that
    are taking courses allocated to him in a specific semester and session
    """
    current_semester = (
        Semester.objects.filter(is_current_semester=True)
        .select_related("session")
        .first()
    )
    if not current_semester or not current_semester.session:
        messages.error(request, "No active session found. Please contact administrator to set a current session.")
        return render(request, "result/add_score_for.html", {"title": "Submit Score"})
    current_session = current_semester.session
    allocated_courses = Course.objects.filter(
        allocated_course__lecturer=request.user,
        semester=current_semester.semester,
    ).distinct()
    course = get_object_or_404(allocated_courses, pk=id)
    enrollments = TakenCourse.objects.filter(course=course).filter(
        Q(semester=current_semester) | Q(semester__isnull=True)
    )

    if request.method == "GET":
        context = {
            "title": "Submit Score",
            "courses": allocated_courses,
            "course": course,
            "students": enrollments,
            "current_session": current_session,
            "current_semester": current_semester,
        }
        return render(request, "result/add_score_for.html", context)

    score_ids = [key for key in request.POST if key != "csrfmiddlewaretoken"]
    enrollment_ids = set(enrollments.values_list("pk", flat=True))
    if not score_ids or any(
        not key.isdecimal() or int(key) not in enrollment_ids for key in score_ids
    ):
        messages.error(
            request,
            "The submitted students are not enrolled in this course and semester.",
        )
        return HttpResponseRedirect(reverse_lazy("add_score_for", kwargs={"id": id}))

    scores_by_id = {}
    for score_id in score_ids:
        values = request.POST.getlist(score_id)
        if len(values) != 5:
            messages.error(request, "Each student must have all five assessment scores.")
            return HttpResponseRedirect(reverse_lazy("add_score_for", kwargs={"id": id}))
        try:
            scores = [Decimal(value) for value in values]
        except InvalidOperation:
            messages.error(request, "Assessment scores must be valid numbers.")
            return HttpResponseRedirect(reverse_lazy("add_score_for", kwargs={"id": id}))
        if any(not score.is_finite() or score < 0 or score > 100 for score in scores):
            messages.error(request, "Assessment scores must be between 0 and 100.")
            return HttpResponseRedirect(reverse_lazy("add_score_for", kwargs={"id": id}))
        scores_by_id[int(score_id)] = scores

    with transaction.atomic():
        locked_enrollments = enrollments.select_for_update().filter(
            pk__in=scores_by_id
        ).select_related("student")
        for enrollment in locked_enrollments:
            (
                enrollment.assignment,
                enrollment.mid_exam,
                enrollment.quiz,
                enrollment.attendance,
                enrollment.final_exam,
            ) = scores_by_id[enrollment.pk]
            enrollment.save()

            result = Result.objects.filter(
                student=enrollment.student,
                semester=current_semester.semester,
                session=current_session.session,
                level=enrollment.student.level,
            ).order_by("pk").first()
            if result is None:
                Result.objects.create(
                    student=enrollment.student,
                    gpa=enrollment.calculate_gpa(),
                    cgpa=enrollment.calculate_cgpa(),
                    semester=current_semester.semester,
                    session=current_session.session,
                    level=enrollment.student.level,
                )
            else:
                result.gpa = enrollment.calculate_gpa()
                result.cgpa = enrollment.calculate_cgpa()
                result.save(update_fields=("gpa", "cgpa"))

    messages.success(request, "Successfully recorded assessment scores.")
    return HttpResponseRedirect(reverse_lazy("add_score_for", kwargs={"id": id}))


# ########################################################


@login_required
@student_required
def grade_result(request):
    student = Student.objects.get(student__pk=request.user.id)
    courses = TakenCourse.objects.filter(student__student__pk=request.user.id).filter(
        course__level=student.level
    )
    # total_credit_in_semester = 0
    results = Result.objects.filter(student__student__pk=request.user.id)

    result_set = set()

    for result in results:
        result_set.add(result.session)

    sorted_result = sorted(result_set)

    total_first_semester_credit = 0
    total_sec_semester_credit = 0
    for i in courses:
        if i.course.semester == "First":
            total_first_semester_credit += int(i.course.credit)
        if i.course.semester == "Second":
            total_sec_semester_credit += int(i.course.credit)

    previousCGPA = 0
    # previousLEVEL = 0
    # calculate_cgpa
    for i in results:
        previousLEVEL = i.level
        try:
            a = Result.objects.get(
                student__student__pk=request.user.id,
                level=previousLEVEL,
                semester="Second",
            )
            previousCGPA = a.cgpa
            break
        except:
            previousCGPA = 0

    context = {
        "courses": courses,
        "results": results,
        "sorted_result": sorted_result,
        "student": student,
        "total_first_semester_credit": total_first_semester_credit,
        "total_sec_semester_credit": total_sec_semester_credit,
        "total_first_and_second_semester_credit": total_first_semester_credit
        + total_sec_semester_credit,
        "previousCGPA": previousCGPA,
    }

    return render(request, "result/grade_results.html", context)


@login_required
@student_required
def assessment_result(request):
    student = Student.objects.get(student__pk=request.user.id)
    courses = TakenCourse.objects.filter(
        student__student__pk=request.user.id, course__level=student.level
    )
    result = Result.objects.filter(student__student__pk=request.user.id)

    context = {
        "courses": courses,
        "result": result,
        "student": student,
    }

    return render(request, "result/assessment_results.html", context)


@login_required
@lecturer_required
def result_sheet_pdf_view(request, id):
    current_semester = Semester.objects.get(is_current_semester=True)
    current_session = Session.objects.get(is_current_session=True)
    result = TakenCourse.objects.filter(course__pk=id).filter(
        Q(semester=current_semester) | Q(semester__isnull=True)
    )
    course = get_object_or_404(Course, id=id)
    no_of_pass = result.filter(comment="PASS").count()
    no_of_fail = result.filter(comment="FAIL").count()
    fname = (
        str(current_semester)
        + "_semester_"
        + str(current_session)
        + "_"
        + str(course)
        + "_resultSheet.pdf"
    )
    fname = fname.replace("/", "-")
    flocation = settings.MEDIA_ROOT + "/result_sheet/" + fname

    doc = SimpleDocTemplate(
        flocation,
        rightMargin=0,
        leftMargin=6.5 * CM,
        topMargin=0.3 * CM,
        bottomMargin=0,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="ParagraphTitle", fontSize=11, fontName="FreeSansBold")
    )
    Story = [Spacer(1, 0.2)]
    style = styles["Normal"]

    # picture = request.user.picture
    # l_pic = Image(picture, 1*inch, 1*inch)
    # l_pic.__setattr__("_offs_x", 200)
    # l_pic.__setattr__("_offs_y", -130)
    # Story.append(l_pic)

    # logo = settings.MEDIA_ROOT + "/logo/logo-mini.png"
    # im_logo = Image(logo, 1*inch, 1*inch)
    # im_logo.__setattr__("_offs_x", -218)
    # im_logo.__setattr__("_offs_y", -60)
    # Story.append(im_logo)

    print("\nsettings.MEDIA_ROOT", settings.MEDIA_ROOT)
    print("\nsettings.STATICFILES_DIRS[0]", settings.STATICFILES_DIRS[0])
    logo = settings.STATICFILES_DIRS[0] + "/img/brand.png"
    im = Image(logo, 1 * inch, 1 * inch)
    im.__setattr__("_offs_x", -200)
    im.__setattr__("_offs_y", -45)
    Story.append(im)

    style = getSampleStyleSheet()
    normal = style["Normal"]
    normal.alignment = TA_CENTER
    normal.fontName = "Helvetica"
    normal.fontSize = 12
    normal.leading = 15
    title = (
        "<b> "
        + str(current_semester)
        + " Semester "
        + str(current_session)
        + " Result Sheet</b>"
    )
    title = Paragraph(title.upper(), normal)
    Story.append(title)
    Story.append(Spacer(1, 0.1 * inch))

    style = getSampleStyleSheet()
    normal = style["Normal"]
    normal.alignment = TA_CENTER
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    normal.leading = 15
    title = "<b>Course lecturer: " + request.user.get_full_name + "</b>"
    title = Paragraph(title.upper(), normal)
    Story.append(title)
    Story.append(Spacer(1, 0.1 * inch))

    normal = style["Normal"]
    normal.alignment = TA_CENTER
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    normal.leading = 15
    level = result.filter(course_id=id).first()
    title = "<b>Level: </b>" + str(level.course.level)
    title = Paragraph(title.upper(), normal)
    Story.append(title)
    Story.append(Spacer(1, 0.6 * inch))

    elements = []
    count = 0
    header = [("S/N", "ID NO.", "FULL NAME", "TOTAL", "GRADE", "POINT", "COMMENT")]

    table_header = Table(header, [inch], [0.5 * inch])
    table_header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.black),
                ("TEXTCOLOR", (1, 0), (-1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.cyan),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    Story.append(table_header)

    for student in result:
        data = [
            (
                count + 1,
                student.student.student.username.upper(),
                Paragraph(
                    student.student.student.get_full_name.capitalize(), styles["Normal"]
                ),
                student.total,
                student.grade,
                student.point,
                student.comment,
            )
        ]
        color = colors.black
        if student.grade == "F":
            color = colors.red
        count += 1

        t_body = Table(data, colWidths=[inch])
        t_body.setStyle(
            TableStyle(
                [
                    ("INNERGRID", (0, 0), (-1, -1), 0.05, colors.black),
                    ("BOX", (0, 0), (-1, -1), 0.1, colors.black),
                ]
            )
        )
        Story.append(t_body)

    Story.append(Spacer(1, 1 * inch))
    style_right = ParagraphStyle(
        name="right", parent=styles["Normal"], alignment=TA_RIGHT
    )
    tbl_data = [
        [
            Paragraph("<b>Date:</b>_____________________________", styles["Normal"]),
            Paragraph("<b>No. of PASS:</b> " + str(no_of_pass), style_right),
        ],
        [
            Paragraph(
                "<b>Siganture / Stamp:</b> _____________________________",
                styles["Normal"],
            ),
            Paragraph("<b>No. of FAIL: </b>" + str(no_of_fail), style_right),
        ],
    ]
    tbl = Table(tbl_data)
    Story.append(tbl)

    doc.build(Story)

    fs = FileSystemStorage(settings.MEDIA_ROOT + "/result_sheet")
    with fs.open(fname) as pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = "inline; filename=" + fname + ""
        return response
    return response


@login_required
@student_required
def course_registration_form(request):
    current_session = Session.objects.get(is_current_session=True)
    courses = TakenCourse.objects.filter(student__student__id=request.user.id)
    fname = request.user.username + ".pdf"
    fname = fname.replace("/", "-")
    # flocation = '/tmp/' + fname
    # print(MEDIA_ROOT + "\\" + fname)
    flocation = settings.MEDIA_ROOT + "/registration_form/" + fname
    doc = SimpleDocTemplate(
        flocation, rightMargin=15, leftMargin=15, topMargin=0, bottomMargin=0
    )
    styles = getSampleStyleSheet()

    Story = [Spacer(1, 0.5)]
    Story.append(Spacer(1, 0.4 * inch))
    style = styles["Normal"]

    style = getSampleStyleSheet()
    normal = style["Normal"]
    normal.alignment = TA_CENTER
    normal.fontName = "Helvetica"
    normal.fontSize = 12
    normal.leading = 18
    title = "<b>EZOD UNIVERSITY OF TECHNOLOGY, ADAMA</b>"  # TODO: Make this dynamic
    title = Paragraph(title.upper(), normal)
    Story.append(title)
    style = getSampleStyleSheet()

    school = style["Normal"]
    school.alignment = TA_CENTER
    school.fontName = "Helvetica"
    school.fontSize = 10
    school.leading = 18
    school_title = (
        "<b>SCHOOL OF ELECTRICAL ENGINEERING & COMPUTING</b>"  # TODO: Make this dynamic
    )
    school_title = Paragraph(school_title.upper(), school)
    Story.append(school_title)

    style = getSampleStyleSheet()
    Story.append(Spacer(1, 0.1 * inch))
    department = style["Normal"]
    department.alignment = TA_CENTER
    department.fontName = "Helvetica"
    department.fontSize = 9
    department.leading = 18
    department_title = (
        "<b>DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING</b>"  # TODO: Make this dynamic
    )
    department_title = Paragraph(department_title, department)
    Story.append(department_title)
    Story.append(Spacer(1, 0.3 * inch))

    title = "<b><u>STUDENT COURSE REGISTRATION FORM</u></b>"
    title = Paragraph(title.upper(), normal)
    Story.append(title)
    student = Student.objects.get(student__pk=request.user.id)

    tbl_data = [
        [
            Paragraph(
                "<b>Registration Number : " + request.user.username.upper() + "</b>",
                styles["Normal"],
            )
        ],
        [
            Paragraph(
                "<b>Name : " + request.user.get_full_name.upper() + "</b>",
                styles["Normal"],
            )
        ],
        [
            Paragraph(
                "<b>Session : " + current_session.session.upper() + "</b>",
                styles["Normal"],
            ),
            Paragraph("<b>Level: " + student.level + "</b>", styles["Normal"]),
        ],
    ]
    tbl = Table(tbl_data)
    Story.append(tbl)
    Story.append(Spacer(1, 0.6 * inch))

    style = getSampleStyleSheet()
    semester = style["Normal"]
    semester.alignment = TA_LEFT
    semester.fontName = "Helvetica"
    semester.fontSize = 9
    semester.leading = 18
    semester_title = "<b>FIRST SEMESTER</b>"
    semester_title = Paragraph(semester_title, semester)
    Story.append(semester_title)

    # FIRST SEMESTER
    count = 0
    header = [
        (
            "S/No",
            "Course Code",
            "Course Title",
            "Unit",
            Paragraph("Name, Siganture of course lecturer & Date", style["Normal"]),
        )
    ]
    table_header = Table(header, 1 * [1.4 * inch], 1 * [0.5 * inch])
    table_header.setStyle(
        TableStyle(
            [
                ("ALIGN", (-2, -2), (-2, -2), "CENTER"),
                ("VALIGN", (-2, -2), (-2, -2), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("ALIGN", (-4, 0), (-4, 0), "LEFT"),
                ("VALIGN", (-4, 0), (-4, 0), "MIDDLE"),
                ("ALIGN", (-3, 0), (-3, 0), "LEFT"),
                ("VALIGN", (-3, 0), (-3, 0), "MIDDLE"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )
    Story.append(table_header)

    first_semester_unit = 0
    for course in courses:
        if course.course.semester == settings.FIRST:
            first_semester_unit += int(course.course.credit)
            data = [
                (
                    count + 1,
                    course.course.code.upper(),
                    Paragraph(course.course.title, style["Normal"]),
                    course.course.credit,
                    "",
                )
            ]
            count += 1
            table_body = Table(data, 1 * [1.4 * inch], 1 * [0.3 * inch])
            table_body.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (-2, -2), (-2, -2), "CENTER"),
                        ("ALIGN", (1, 0), (1, 0), "CENTER"),
                        ("ALIGN", (0, 0), (0, 0), "CENTER"),
                        ("ALIGN", (-4, 0), (-4, 0), "LEFT"),
                        ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
                    ]
                )
            )
            Story.append(table_body)

    style = getSampleStyleSheet()
    semester = style["Normal"]
    semester.alignment = TA_LEFT
    semester.fontName = "Helvetica"
    semester.fontSize = 8
    semester.leading = 18
    semester_title = (
        "<b>Total Second First Credit : " + str(first_semester_unit) + "</b>"
    )
    semester_title = Paragraph(semester_title, semester)
    Story.append(semester_title)

    # FIRST SEMESTER ENDS HERE
    Story.append(Spacer(1, 0.6 * inch))

    style = getSampleStyleSheet()
    semester = style["Normal"]
    semester.alignment = TA_LEFT
    semester.fontName = "Helvetica"
    semester.fontSize = 9
    semester.leading = 18
    semester_title = "<b>SECOND SEMESTER</b>"
    semester_title = Paragraph(semester_title, semester)
    Story.append(semester_title)
    # SECOND SEMESTER
    count = 0
    header = [
        (
            "S/No",
            "Course Code",
            "Course Title",
            "Unit",
            Paragraph(
                "<b>Name, Signature of course lecturer & Date</b>", style["Normal"]
            ),
        )
    ]
    table_header = Table(header, 1 * [1.4 * inch], 1 * [0.5 * inch])
    table_header.setStyle(
        TableStyle(
            [
                ("ALIGN", (-2, -2), (-2, -2), "CENTER"),
                ("VALIGN", (-2, -2), (-2, -2), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("ALIGN", (-4, 0), (-4, 0), "LEFT"),
                ("VALIGN", (-4, 0), (-4, 0), "MIDDLE"),
                ("ALIGN", (-3, 0), (-3, 0), "LEFT"),
                ("VALIGN", (-3, 0), (-3, 0), "MIDDLE"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )
    Story.append(table_header)

    second_semester_unit = 0
    for course in courses:
        if course.course.semester == settings.SECOND:
            second_semester_unit += int(course.course.credit)
            data = [
                (
                    count + 1,
                    course.course.code.upper(),
                    Paragraph(course.course.title, style["Normal"]),
                    course.course.credit,
                    "",
                )
            ]
            # color = colors.black
            count += 1
            table_body = Table(data, 1 * [1.4 * inch], 1 * [0.3 * inch])
            table_body.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (-2, -2), (-2, -2), "CENTER"),
                        ("ALIGN", (1, 0), (1, 0), "CENTER"),
                        ("ALIGN", (0, 0), (0, 0), "CENTER"),
                        ("ALIGN", (-4, 0), (-4, 0), "LEFT"),
                        ("TEXTCOLOR", (0, -1), (-1, -1), colors.black),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
                    ]
                )
            )
            Story.append(table_body)

    style = getSampleStyleSheet()
    semester = style["Normal"]
    semester.alignment = TA_LEFT
    semester.fontName = "Helvetica"
    semester.fontSize = 8
    semester.leading = 18
    semester_title = (
        "<b>Total Second Semester Credit : " + str(second_semester_unit) + "</b>"
    )
    semester_title = Paragraph(semester_title, semester)
    Story.append(semester_title)

    Story.append(Spacer(1, 2))
    style = getSampleStyleSheet()
    certification = style["Normal"]
    certification.alignment = TA_JUSTIFY
    certification.fontName = "Helvetica"
    certification.fontSize = 8
    certification.leading = 18
    student = Student.objects.get(student__pk=request.user.id)
    certification_text = (
        "CERTIFICATION OF REGISTRATION: I certify that <b>"
        + str(request.user.get_full_name.upper())
        + "</b>\
    has been duly registered for the <b>"
        + student.level
        + " level </b> of study in the department\
    of COMPUTER SICENCE & ENGINEERING and that the courses and credits \
    registered are as approved by the senate of the University"
    )
    certification_text = Paragraph(certification_text, certification)
    Story.append(certification_text)

    # FIRST SEMESTER ENDS HERE

    logo = settings.STATICFILES_DIRS[0] + "/img/brand.png"
    im_logo = Image(logo, 1 * inch, 1 * inch)
    setattr(im_logo, "_offs_x", -218)
    setattr(im_logo, "_offs_y", 480)
    Story.append(im_logo)

    picture = settings.BASE_DIR + request.user.get_picture()
    im = Image(picture, 1.0 * inch, 1.0 * inch)
    setattr(im, "_offs_x", 218)
    setattr(im, "_offs_y", 550)
    Story.append(im)

    doc.build(Story)
    fs = FileSystemStorage(settings.MEDIA_ROOT + "/registration_form")
    with fs.open(fname) as pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = "inline; filename=" + fname + ""
        return response
    return response

@login_required
def registrar_add_results(request):
    if request.user.is_registrar:
        return render(request, "result/add_score.html")
    return render(request, "core/403.html")


@login_required
def registrar_edit_results(request):
    if not request.user.is_registrar:
        return render(request, "core/403.html")

    # Get the current session and semester
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True).first()

    if not current_session or not current_semester:
        return render(request, "result/add_score_for.html", {
            "course": None,
            "courses": [],
            "students": [],
            "current_session": None,
            "current_semester": None,
        })

    # Get courses and students for the current semester
    courses = Course.objects.filter(semester=current_semester.semester)
    course = courses.first()  # Just for demo; in practice, you can allow selecting course

    students = []
    if course:
        students = TakenCourse.objects.filter(course=course).filter(
            Q(semester=current_semester) | Q(semester__isnull=True)
        )

    return render(request, "result/add_score_for.html", {
        "course": course,
        "courses": courses,
        "students": students,
        "current_session": current_session,
        "current_semester": current_semester,
    })


@login_required
def registrar_view_transcripts(request):
    if request.user.is_registrar:
        return render(request, "result/assessment_results.html")
    return render(request, "core/403.html")

@login_required
def registrar_manage_clearance(request):
    if request.user.is_registrar:
        return render(request, "result/grade_results.html")
    return render(request, "core/403.html")

def manage_clearance_view(request):
    return HttpResponse("Registrar Manage Clearance Page (Placeholder)")
@login_required
@login_required
@student_required
def view_transcripts(request):
    student = Student.objects.get(student__pk=request.user.id)
    results = Result.objects.filter(student=student).order_by('-session')

    context = {
        "student": student,
        "results": results
    }
    return render(request, "result/view_transcripts.html", context)

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def manage_clearance(request):
    return render(request, 'result/manage_clearance.html')


# ########################################################
# Assessment Configuration Views (Lecturer)
# ########################################################
from django.utils import timezone
from .models import AssessmentConfig, AttendanceRecord, ClassSession, CourseAssignment, AssignmentSubmission
from .forms import AssessmentConfigForm, AttendanceRecordForm, ClassSessionForm, CourseAssignmentForm, BulkAttendanceForm
from quiz.models import Quiz, Sitting


@login_required
@lecturer_required
def assessment_config_view(request, course_id):
    """Lecturer configures assessment weights and settings for a course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check if lecturer is allocated to this course
    if not course.allocated_course.filter(lecturer=request.user).exists():
        messages.error(request, "You are not authorized to configure this course.")
        return HttpResponseRedirect(reverse_lazy('add_score'))
    
    # Get or create assessment config for this course
    config, created = AssessmentConfig.objects.get_or_create(course=course)
    
    if request.method == 'POST':
        form = AssessmentConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, f"Assessment configuration for {course.title} updated successfully!")
            return HttpResponseRedirect(reverse_lazy('assessment_config', kwargs={'course_id': course_id}))
    else:
        form = AssessmentConfigForm(instance=config)
    
    context = {
        'title': f'Assessment Config - {course.title}',
        'course': course,
        'form': form,
        'config': config,
    }
    return render(request, 'result/assessment_config.html', context)


@login_required
@lecturer_required
def attendance_management_view(request, course_id):
    """Lecturer manages attendance for a course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check allocation
    if not course.allocated_course.filter(lecturer=request.user).exists():
        messages.error(request, "You are not authorized to manage this course.")
        return HttpResponseRedirect(reverse_lazy('add_score'))
    
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True, session=current_session).first()
    
    # Get students enrolled in this course
    enrolled_students = (
        TakenCourse.objects.filter(
            course=course,
            course__semester=current_semester.semester,
        ).filter(Q(semester=current_semester) | Q(semester__isnull=True))
        if current_semester
        else []
    )
    
    # Get class sessions
    class_sessions = ClassSession.objects.filter(course=course).order_by('-date')[:20]
    
    # Get attendance records
    attendance_records = AttendanceRecord.objects.filter(course=course).order_by('-date')
    
    # Handle POST for creating new class session
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_session':
            date = request.POST.get('session_date')
            topic = request.POST.get('topic', '')
            if date:
                ClassSession.objects.get_or_create(
                    course=course,
                    date=date,
                    defaults={'topic': topic, 'created_by': request.user}
                )
                messages.success(request, f"Class session for {date} created!")
        
        elif action == 'record_attendance':
            date = request.POST.get('attendance_date')
            if date:
                for student_tc in enrolled_students:
                    status = request.POST.get(f'status_{student_tc.student.id}', 'absent')
                    AttendanceRecord.objects.update_or_create(
                        student=student_tc.student,
                        course=course,
                        date=date,
                        defaults={'status': status, 'recorded_by': request.user}
                    )
                messages.success(request, "Attendance recorded successfully!")
        
        return HttpResponseRedirect(reverse_lazy('attendance_management', kwargs={'course_id': course_id}))
    
    # Calculate attendance stats for each student
    student_attendance_stats = []
    for tc in enrolled_students:
        total_sessions = class_sessions.count()
        present_count = AttendanceRecord.objects.filter(
            student=tc.student, course=course, status='present'
        ).count()
        late_count = AttendanceRecord.objects.filter(
            student=tc.student, course=course, status='late'
        ).count()
        absent_count = AttendanceRecord.objects.filter(
            student=tc.student, course=course, status='absent'
        ).count()
        
        attendance_percentage = (present_count + (late_count * 0.5)) / total_sessions * 100 if total_sessions > 0 else 0
        
        student_attendance_stats.append({
            'student': tc.student,
            'present': present_count,
            'late': late_count,
            'absent': absent_count,
            'total_sessions': total_sessions,
            'percentage': round(attendance_percentage, 1)
        })
    
    context = {
        'title': f'Attendance - {course.title}',
        'course': course,
        'enrolled_students': enrolled_students,
        'class_sessions': class_sessions,
        'attendance_records': attendance_records,
        'student_attendance_stats': student_attendance_stats,
        'today': timezone.now().date(),
    }
    return render(request, 'result/attendance_management.html', context)


@login_required
@lecturer_required
def course_assignments_view(request, course_id):
    """Lecturer manages assignments for a course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check allocation
    if not course.allocated_course.filter(lecturer=request.user).exists():
        messages.error(request, "You are not authorized to manage this course.")
        return HttpResponseRedirect(reverse_lazy('add_score'))
    
    assignments = CourseAssignment.objects.filter(course=course)
    
    # Handle POST for creating assignment
    if request.method == 'POST':
        form = CourseAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            assignment.created_by = request.user
            assignment.save()
            messages.success(request, f"Assignment '{assignment.title}' created successfully!")
            return HttpResponseRedirect(reverse_lazy('course_assignments', kwargs={'course_id': course_id}))
    else:
        form = CourseAssignmentForm()
    
    context = {
        'title': f'Assignments - {course.title}',
        'course': course,
        'assignments': assignments,
        'form': form,
    }
    return render(request, 'result/course_assignments.html', context)


# ########################################################
# Student Assessment Recap View
# ########################################################
@login_required
@student_required
@login_required
@student_required
def student_assessment_recap_view(request):
    """Student views their comprehensive assessment recap"""
    student = get_object_or_404(Student, student=request.user)
    
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True, session=current_session).first()
    
    # Get enrolled courses
    taken_courses = TakenCourse.objects.filter(student=student)
    if current_semester:
        current_taken_courses = taken_courses.filter(
            course__semester=current_semester.semester
        ).filter(Q(semester=current_semester) | Q(semester__isnull=True))
    else:
        current_taken_courses = taken_courses
    
    # Build comprehensive recap for each course
    course_recaps = []
    for tc in current_taken_courses:
        course = tc.course
        
        # Attendance data
        attendance_records = AttendanceRecord.objects.filter(student=student, course=course)
        total_classes = ClassSession.objects.filter(course=course).count()
        present_count = attendance_records.filter(status='present').count()
        late_count = attendance_records.filter(status='late').count()
        absent_count = attendance_records.filter(status='absent').count()
        attendance_percentage = (present_count + (late_count * 0.5)) / total_classes * 100 if total_classes > 0 else 0
        
        # Quiz attempts
        quiz_sittings = Sitting.objects.filter(user=request.user, course=course, complete=True)
        quizzes_taken = quiz_sittings.count()
        quiz_scores = [(s.quiz.title, s.get_percent_correct) for s in quiz_sittings]
        avg_quiz_score = sum(s[1] for s in quiz_scores) / len(quiz_scores) if quiz_scores else 0
        
        # Assignment data
        assignments = CourseAssignment.objects.filter(course=course, is_published=True)
        submissions = AssignmentSubmission.objects.filter(student=student, assignment__course=course)
        assignments_submitted = submissions.count()
        total_assignments = assignments.count()
        
        # Assessment config
        try:
            config = AssessmentConfig.objects.get(course=course)
        except AssessmentConfig.DoesNotExist:
            config = None
        
        course_recaps.append({
            'course': course,
            'taken_course': tc,
            'config': config,
            # Scores from TakenCourse
            'assignment_score': tc.assignment,
            'mid_exam_score': tc.mid_exam,
            'quiz_score': tc.quiz,
            'attendance_score': tc.attendance,
            'final_exam_score': tc.final_exam,
            'total': tc.total,
            'grade': tc.grade,
            'point': tc.point,
            # Attendance breakdown
            'attendance': {
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'total_classes': total_classes,
                'percentage': round(attendance_percentage, 1),
                'records': attendance_records.order_by('-date')[:10]
            },
            # Quiz breakdown
            'quizzes': {
                'taken': quizzes_taken,
                'scores': quiz_scores,
                'average': round(avg_quiz_score, 1),
                'sittings': quiz_sittings[:5]
            },
            # Assignment breakdown
            'assignments': {
                'submitted': assignments_submitted,
                'total': total_assignments,
                'items': assignments,
                'submissions': submissions
            }
        })
    
    # Overall stats
    total_courses = current_taken_courses.count()
    total_credits = sum(tc.course.credit for tc in current_taken_courses)
    
    # Calculate current GPA
    if current_taken_courses.exists():
        gpa = current_taken_courses.first().calculate_gpa()
        cgpa = current_taken_courses.first().calculate_cgpa()
    else:
        gpa = cgpa = 0
    
    context = {
        'title': 'My Assessment Recap',
        'student': student,
        'current_session': current_session,
        'current_semester': current_semester,
        'course_recaps': course_recaps,
        'total_courses': total_courses,
        'total_credits': total_credits,
        'gpa': gpa,
        'cgpa': cgpa,
    }
    return render(request, 'result/student_assessment_recap.html', context)


@login_required
@student_required
def student_course_detail_view(request, course_id):
    """Student views detailed assessment info for a specific course"""
    student = get_object_or_404(Student, student=request.user)
    course = get_object_or_404(Course, id=course_id)
    
    # Check enrollment
    current_semester = Semester.objects.filter(is_current_semester=True).first()
    enrollment_query = TakenCourse.objects.filter(student=student, course=course)
    if current_semester:
        enrollment_query = enrollment_query.filter(
            Q(semester=current_semester) | Q(semester__isnull=True)
        )
    taken_course = enrollment_query.order_by("-semester_id").first()
    if not taken_course:
        messages.error(request, "You are not enrolled in this course.")
        return HttpResponseRedirect(reverse_lazy('student_assessment_recap'))
    
    # Attendance records
    attendance_records = AttendanceRecord.objects.filter(student=student, course=course).order_by('-date')
    total_classes = ClassSession.objects.filter(course=course).count()
    present_count = attendance_records.filter(status='present').count()
    late_count = attendance_records.filter(status='late').count()
    
    # Quiz attempts
    quiz_sittings = Sitting.objects.filter(user=request.user, course=course, complete=True).order_by('-end')
    
    # Assignments
    assignments = CourseAssignment.objects.filter(course=course, is_published=True)
    submissions = AssignmentSubmission.objects.filter(student=student, assignment__course=course)
    
    # Build assignment list with submission status
    assignment_list = []
    for assignment in assignments:
        try:
            submission = submissions.get(assignment=assignment)
            assignment_list.append({
                'assignment': assignment,
                'submitted': True,
                'submission': submission
            })
        except AssignmentSubmission.DoesNotExist:
            assignment_list.append({
                'assignment': assignment,
                'submitted': False,
                'submission': None
            })
    
    # Assessment config
    try:
        config = AssessmentConfig.objects.get(course=course)
    except AssessmentConfig.DoesNotExist:
        config = None
    
    context = {
        'title': f'{course.title} - Assessment Details',
        'student': student,
        'course': course,
        'taken_course': taken_course,
        'config': config,
        'attendance_records': attendance_records,
        'attendance_stats': {
            'total_classes': total_classes,
            'present': present_count,
            'late': late_count,
            'absent': attendance_records.filter(status='absent').count(),
            'excused': attendance_records.filter(status='excused').count(),
        },
        'quiz_sittings': quiz_sittings,
        'assignment_list': assignment_list,
    }
    return render(request, 'result/student_course_detail.html', context)


# ########################################################
# Comprehensive Assessment Hub
# ########################################################
from course.models import CourseAllocation
from accounts.models import User

@login_required
def assessment_hub_view(request):
    """
    Comprehensive Assessment Hub - Role-based view showing all assessment-related 
    information and actions for each user type.
    """
    from quiz.models import Quiz, Sitting
    from course.models import CourseAllocation
    from .models import (
        AssignmentSubmission,
        AttendanceRecord,
        ClassSession,
        CourseAssignment,
    )
    
    user = request.user
    current_session = Session.objects.filter(is_current_session=True).first()
    current_semester = Semester.objects.filter(is_current_semester=True, session=current_session).first()
    
    context = {
        'title': 'Assessment Hub',
        'current_session': current_session,
        'current_semester': current_semester,
        'user': user,
    }
    
    # ===== STUDENT VIEW =====
    if user.is_student:
        student = Student.objects.filter(student=user).first()
        if not student:
            messages.error(request, "Student profile not found.")
            return render(request, 'result/assessment_hub_student.html', context)
        
        # Get enrolled courses
        taken_courses = TakenCourse.objects.filter(student=student)
        current_courses = taken_courses.filter(course__semester=current_semester.semester) if current_semester else taken_courses
        
        # Pending actions for student
        pending_quizzes = []
        pending_assignments = []
        upcoming_exams = []
        low_attendance_courses = []
        
        for tc in current_courses:
            course = tc.course
            
            # Find quizzes not yet attempted
            available_quizzes = Quiz.objects.filter(course=course, draft=False)
            for quiz in available_quizzes:
                if not Sitting.objects.filter(user=user, quiz=quiz, complete=True).exists():
                    pending_quizzes.append({'quiz': quiz, 'course': course})
            
            # Find pending assignments
            course_assignments = CourseAssignment.objects.filter(
                course=course,
                is_published=True,
            )
            for assignment in course_assignments:
                if not AssignmentSubmission.objects.filter(student=student, assignment=assignment).exists():
                    pending_assignments.append({'assignment': assignment, 'course': course})
            
            # Check attendance
            total_classes = ClassSession.objects.filter(course=course).count()
            present = AttendanceRecord.objects.filter(student=student, course=course, status='present').count()
            if total_classes > 0:
                attendance_rate = (present / total_classes) * 100
                if attendance_rate < 75:
                    low_attendance_courses.append({
                        'course': course,
                        'rate': round(attendance_rate, 1),
                        'present': present,
                        'total': total_classes
                    })
        
        # Recent grades
        recent_results = Result.objects.filter(student=student).order_by('-id')[:5]
        
        # Calculate GPA
        gpa = current_courses.first().calculate_gpa() if current_courses.exists() else 0
        cgpa = current_courses.first().calculate_cgpa() if current_courses.exists() else 0
        
        context.update({
            'student': student,
            'current_courses': current_courses,
            'pending_quizzes': pending_quizzes[:5],
            'pending_assignments': pending_assignments[:5],
            'low_attendance_courses': low_attendance_courses,
            'recent_results': recent_results,
            'gpa': gpa,
            'cgpa': cgpa,
            'total_courses': current_courses.count(),
            'total_pending_quizzes': len(pending_quizzes),
            'total_pending_assignments': len(pending_assignments),
        })
        return render(request, 'result/assessment_hub_student.html', context)
    
    # ===== LECTURER VIEW =====
    elif user.is_lecturer:
        # Get allocated courses
        allocations = CourseAllocation.objects.filter(lecturer=user)
        allocated_courses = []
        pending_actions = []
        
        for allocation in allocations:
            # CourseAllocation has ManyToManyField 'courses', not single 'course'
            for course in allocation.courses.all():
                if current_semester and course.semester != current_semester.semester:
                    continue
                    
                # Get students enrolled
                enrolled_students = TakenCourse.objects.filter(course=course)
                
                # Pending grading
                ungraded_count = enrolled_students.filter(total=0).count()
                
                # Add to pending actions if there are ungraded students
                if ungraded_count > 0:
                    pending_actions.append({
                        'type': 'ungraded',
                        'course': course,
                        'count': ungraded_count,
                    })
                
                # Quiz submissions to mark - get individual quizzes
                from quiz.models import Quiz
                course_quizzes = Quiz.objects.filter(course=course)
                pending_quiz_marking = 0
                
                for quiz in course_quizzes:
                    quiz_pending = Sitting.objects.filter(
                        quiz=quiz, 
                        complete=True,
                    ).exclude(
                        current_score__gt=0  # Exclude fully auto-graded
                    ).count()
                    
                    # For essay quizzes that need manual marking
                    essay_pending = Sitting.objects.filter(
                        quiz=quiz,
                        complete=True,
                    ).count()
                    
                    if essay_pending > 0:
                        pending_actions.append({
                            'type': 'quiz_marking',
                            'course': course,
                            'quiz': quiz,
                            'count': essay_pending,
                        })
                        pending_quiz_marking += essay_pending
                
                # Attendance stats
                total_sessions = ClassSession.objects.filter(course=course).count()
                
                # Assessment config status
                try:
                    config = AssessmentConfig.objects.get(course=course)
                    config_complete = True
                except AssessmentConfig.DoesNotExist:
                    config_complete = False
                
                # Get all assignments for this course with submission stats
                assignments = CourseAssignment.objects.filter(course=course)
                assignments_list = []
                total_pending_submissions = 0
                
                for assignment in assignments:
                    pending_count = AssignmentSubmission.objects.filter(
                        assignment=assignment,
                        score__isnull=True
                    ).count()
                    total_count = AssignmentSubmission.objects.filter(assignment=assignment).count()
                    
                    assignments_list.append({
                        'assignment': assignment,
                        'pending_count': pending_count,
                        'total_submissions': total_count,
                    })
                    
                    if pending_count > 0:
                        pending_actions.append({
                            'type': 'assignment',
                            'course': course,
                            'assignment': assignment,
                            'count': pending_count,
                        })
                        total_pending_submissions += pending_count
                
                # Get Canvas-style assignments if the assignment app exists
                canvas_assignments_list = []
                if apps.is_installed("assignment"):
                    from assignment.models import Assignment as CanvasAssignment, AssignmentSubmission as CanvasSubmission
                    canvas_assignments = CanvasAssignment.objects.filter(course=course)
                    
                    for canvas_assignment in canvas_assignments:
                        canvas_pending = CanvasSubmission.objects.filter(
                            assignment=canvas_assignment,
                            status__in=['submitted', 'resubmitted']
                        ).count()
                        canvas_total = CanvasSubmission.objects.filter(assignment=canvas_assignment).count()
                        
                        canvas_assignments_list.append({
                            'assignment': canvas_assignment,
                            'pending_count': canvas_pending,
                            'total_submissions': canvas_total,
                        })
                        
                        if canvas_pending > 0:
                            pending_actions.append({
                                'type': 'canvas_assignment',
                                'course': course,
                                'assignment': canvas_assignment,
                                'count': canvas_pending,
                            })
                            total_pending_submissions += canvas_pending
                
                allocated_courses.append({
                    'course': course,
                    'enrolled_students': enrolled_students.count(),
                    'ungraded': ungraded_count,
                    'pending_quiz_marking': pending_quiz_marking,
                    'total_sessions': total_sessions,
                    'config_complete': config_complete,
                    'assignments': assignments_list,
                    'canvas_assignments': canvas_assignments_list,
                    'assignments_count': len(assignments_list) + len(canvas_assignments_list),
                    'pending_submissions': total_pending_submissions,
                })
        
        # Sort pending actions by count (most urgent first)
        pending_actions.sort(key=lambda x: x['count'], reverse=True)
        
        # Overall stats
        total_students = sum(c['enrolled_students'] for c in allocated_courses)
        total_ungraded = sum(c['ungraded'] for c in allocated_courses)
        total_pending_marking = sum(c['pending_quiz_marking'] for c in allocated_courses)
        total_pending_assignments = sum(c['pending_submissions'] for c in allocated_courses)
        
        context.update({
            'courses': allocated_courses,
            'total_courses': len(allocated_courses),
            'total_students': total_students,
            'total_ungraded': total_ungraded,
            'total_quizzes_pending': total_pending_marking,
            'total_assignments_pending': total_pending_assignments,
            'pending_actions': pending_actions[:10],  # Show top 10 pending actions
        })
        return render(request, 'result/assessment_hub_lecturer.html', context)
    
    # ===== ADMIN/SUPERUSER VIEW =====
    elif user.is_superuser or user.is_faculty_admin:
        # System-wide statistics
        total_students = Student.objects.count()
        total_lecturers = User.objects.filter(is_lecturer=True).count()
        total_courses = Course.objects.count()
        
        # Current semester courses
        if current_semester:
            active_courses = Course.objects.filter(semester=current_semester.semester)
        else:
            active_courses = Course.objects.all()
        
        # Grading overview
        all_taken_courses = TakenCourse.objects.all()
        total_taken_courses = all_taken_courses.count()
        graded_count = all_taken_courses.exclude(total=0).count()
        ungraded_count = all_taken_courses.filter(total=0).count()
        total_graded = graded_count
        
        # Grade distribution counts
        grade_a_count = TakenCourse.objects.filter(grade__in=['A+', 'A']).count()
        grade_b_count = TakenCourse.objects.filter(grade__in=['B+', 'B', 'B-']).count()
        grade_c_count = TakenCourse.objects.filter(grade__in=['C+', 'C', 'C-']).count()
        grade_d_count = TakenCourse.objects.filter(grade='D').count()
        grade_f_count = TakenCourse.objects.filter(grade='F').count()
        
        # Grade distribution percentages
        grade_a_percent = round((grade_a_count / total_graded * 100), 1) if total_graded > 0 else 0
        grade_b_percent = round((grade_b_count / total_graded * 100), 1) if total_graded > 0 else 0
        grade_c_percent = round((grade_c_count / total_graded * 100), 1) if total_graded > 0 else 0
        grade_d_percent = round((grade_d_count / total_graded * 100), 1) if total_graded > 0 else 0
        grade_f_percent = round((grade_f_count / total_graded * 100), 1) if total_graded > 0 else 0
        
        # Pass/Fail rates
        pass_count = TakenCourse.objects.filter(comment='PASS').count()
        fail_count = TakenCourse.objects.filter(comment='FAIL').count()
        pass_rate = round((pass_count / total_graded * 100), 1) if total_graded > 0 else 0
        fail_rate = round((fail_count / total_graded * 100), 1) if total_graded > 0 else 0
        
        # Average GPA calculation
        from django.db.models import Avg
        avg_gpa_result = all_taken_courses.exclude(point=0).aggregate(avg=Avg('point'))
        average_gpa = round(avg_gpa_result['avg'], 2) if avg_gpa_result['avg'] else 0
        
        # Recent quiz activity
        recent_sittings = Sitting.objects.filter(complete=True).order_by('-end')[:10]
        
        # Courses needing attention (low grading completion or high fail rate)
        courses_needing_attention = []
        for course in active_courses[:20]:
            enrolled = TakenCourse.objects.filter(course=course).count()
            graded = TakenCourse.objects.filter(course=course).exclude(total=0).count()
            failed = TakenCourse.objects.filter(course=course, comment='FAIL').count()
            if enrolled > 0:
                completion_rate = (graded / enrolled) * 100
                course_fail_rate = (failed / graded * 100) if graded > 0 else 0
                if completion_rate < 50 or course_fail_rate > 20:
                    # Get lecturer - CourseAllocation has ManyToMany 'courses'
                    allocation = CourseAllocation.objects.filter(courses=course).first()
                    lecturer = allocation.lecturer.get_full_name if allocation else None
                    courses_needing_attention.append({
                        'course': course,
                        'enrolled': enrolled,
                        'ungraded': enrolled - graded,
                        'fail_rate': round(course_fail_rate, 1),
                        'lecturer': lecturer,
                    })
        
        context.update({
            'total_students': total_students,
            'total_lecturers': total_lecturers,
            'total_courses': total_courses,
            'total_taken_courses': total_taken_courses,
            'active_courses': active_courses.count(),
            'graded_count': graded_count,
            'ungraded_count': ungraded_count,
            'total_graded': total_graded,
            'grade_a_count': grade_a_count,
            'grade_b_count': grade_b_count,
            'grade_c_count': grade_c_count,
            'grade_d_count': grade_d_count,
            'grade_f_count': grade_f_count,
            'grade_a_percent': grade_a_percent,
            'grade_b_percent': grade_b_percent,
            'grade_c_percent': grade_c_percent,
            'grade_d_percent': grade_d_percent,
            'grade_f_percent': grade_f_percent,
            'pass_rate': pass_rate,
            'fail_rate': fail_rate,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'average_gpa': average_gpa,
            'recent_sittings': recent_sittings,
            'courses_needing_attention': courses_needing_attention[:5],
        })
        return render(request, 'result/assessment_hub_admin.html', context)
    
    # Default fallback
    return render(request, 'result/assessment_hub_student.html', context)

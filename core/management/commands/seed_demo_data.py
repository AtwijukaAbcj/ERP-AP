from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import DepartmentHead, Student
from admissions.models import Application
from clinical.models import ClinicalLogEntry, ClinicalPlacement, Ward
from course.models import Course, CourseOffer, Faculty, Program
from core.models import NewsAndEvents, Semester, Session
from finance.models import (
    FeeCategory,
    Invoice,
    InvoiceItem,
    InvoicePayment,
    Staff,
    StaffCategory,
    StaffDepartment,
)
from procurement.models import (
    ProcurementDepartment,
    ProcurementStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseRequisition,
    Supplier,
    SupplierCategory,
)
from result.models import (
    AssignmentSubmission,
    AttendanceRecord,
    ClassSession,
    CourseAssignment,
    Result,
    TakenCourse,
)


class Command(BaseCommand):
    help = "Create clearly labeled demo records in a local DEBUG SQLite database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Create the sample inside a transaction and roll it back.",
        )
        parser.add_argument(
            "--procurement-only",
            action="store_true",
            help="Create only fictional procurement demo records.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG or connection.vendor != "sqlite":
            raise CommandError(
                "Demo data may only be seeded when DEBUG is enabled and the "
                "configured database is SQLite."
            )

        self.created_count = 0
        today = timezone.localdate()
        with transaction.atomic():
            if options["procurement_only"]:
                self._seed_procurement(today)
            else:
                self._seed(today)
            created_count = self.created_count
            if options["dry_run"]:
                transaction.set_rollback(True)

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete: {created_count} demo records would be created; "
                    "all changes were rolled back."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo data is ready. Created {created_count} records; "
                    "existing records were left unchanged."
                )
            )

    def _ensure(self, model, lookup, defaults=None):
        instance, created = model.objects.get_or_create(
            **lookup,
            defaults=defaults or {},
        )
        if created:
            self.created_count += 1
        return instance

    def _demo_user(self, username, email, last_name, **flags):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            if User.objects.filter(email=email).exists():
                raise CommandError(
                    f"Refusing to reuse the existing email address {email!r}."
                )
            user = User(
                username=username,
                email=email,
                first_name="Demo",
                last_name=last_name,
            )
            user.set_unusable_password()
            user.save(force_insert=True)
            User.objects.filter(pk=user.pk).update(**flags)
            user.refresh_from_db()
            self.created_count += 1
        elif (
            user.email != email
            or user.first_name != "Demo"
            or user.last_name != last_name
            or any(getattr(user, name) != value for name, value in flags.items())
            or user.has_usable_password()
        ):
            raise CommandError(
                f"Refusing to use the existing account {username!r}: it does not "
                "match the expected demo identity or has a usable password."
            )
        return user

    def _seed(self, today):
        next_year = today.year + 1
        academic_year = f"{today.year}/{next_year}"

        faculty = self._ensure(
            Faculty,
            {"name": "DEMO - Health Sciences"},
            {"description": "Fictional department for application demonstrations."},
        )
        program = self._ensure(
            Program,
            {"title": "DEMO - Psychiatric Nursing"},
            {"summary": "Fictional programme used for demo records.", "faculty": faculty},
        )
        session = self._ensure(
            Session,
            {"session": f"DEMO {academic_year}"},
            {"is_current_session": False, "next_session_begins": today + timedelta(days=180)},
        )
        semester = self._ensure(
            Semester,
            {"session": session, "semester": "First"},
            {
                "is_current_semester": False,
                "registration_open_date": today - timedelta(days=14),
                "registration_close_date": today + timedelta(days=45),
                "add_drop_open_date": today - timedelta(days=7),
                "add_drop_close_date": today + timedelta(days=14),
                "next_semester_begins": today + timedelta(days=90),
            },
        )

        student_user = self._demo_user(
            "demo_student",
            "demo.student@example.test",
            "Student",
            is_student=True,
            gender="F",
            phone="+256700000101",
        )
        supervisor = self._demo_user(
            "demo_supervisor",
            "demo.supervisor@example.test",
            "Supervisor",
            is_lecturer=True,
            gender="M",
            phone="+256700000102",
        )
        department_head_user = self._demo_user(
            "demo_department_head",
            "demo.departmenthead@example.test",
            "Department Head",
            is_dep_head=True,
        )
        finance_user = self._demo_user(
            "demo_finance",
            "demo.finance@example.test",
            "Finance Officer",
            is_finance=True,
        )
        staff_category = self._ensure(
            StaffCategory,
            {"name": "DEMO - Administrative Staff"},
            {"description": "Fictional staff category."},
        )
        staff_department = self._ensure(
            StaffDepartment,
            {"name": "DEMO - Finance Department", "code": "DEMO-FIN"},
            {"faculty": faculty, "head": finance_user},
        )
        self._ensure(
            Staff,
            {"user": finance_user},
            {
                "category": staff_category,
                "qualification": "DEMO - Diploma in Business Administration",
                "department": staff_department,
                "employee_id": f"DEMO-EMP-{finance_user.pk:06d}",
                "job_title": "Finance Officer",
                "date_hired": today - timedelta(days=90),
            },
        )
        registration_number = f"DEMO-ERPAP-{student_user.pk:06d}"
        student = Student.objects.filter(student=student_user).first()
        if student:
            if student.registration_number != registration_number:
                raise CommandError(
                    "The existing demo student has a different registration number; "
                    "it was left unchanged."
                )
        elif Student.objects.filter(registration_number=registration_number).exists():
            raise CommandError(
                f"Refusing to reuse the existing registration number "
                f"{registration_number!r}."
            )
        else:
            student = self._ensure(
                Student,
                {"student": student_user},
                {
                    "registration_number": registration_number,
                    "program": program,
                    "level": "Bachelor",
                    "year": 1,
                    "semester": semester,
                    "cohort": f"DEMO {academic_year}",
                    "date_of_birth": today - timedelta(days=25 * 365),
                    "admission_date": today - timedelta(days=60),
                    "expected_completion_date": today + timedelta(days=365 * 3),
                    "next_of_kin_name": "Demo Contact",
                    "next_of_kin_phone": "+256700000103",
                    "status": Student.Status.ACTIVE,
                },
            )
        application = self._ensure(
            Application,
            {"application_number": "DEMO-APP-001"},
            {
                "first_name": "Demo",
                "last_name": "Student",
                "date_of_birth": today - timedelta(days=25 * 365),
                "email": student_user.email,
                "phone": student_user.phone or "",
                "address": "Demo address - not a real applicant",
                "next_of_kin_name": "Demo Contact",
                "next_of_kin_phone": "+256700000103",
                "program": program,
                "intake": "DEMO Intake",
                "academic_year": academic_year,
                "previous_education": "Fictional demo education history.",
                "status": Application.Status.ACCEPTED,
                "decision_notes": "Fictional application linked to the demo student.",
                "linked_student": student,
            },
        )
        if application.linked_student_id != student.pk:
            raise CommandError(
                "The existing DEMO-APP-001 record is not linked to the demo student; "
                "it was left unchanged."
            )

        department_head = self._ensure(
            DepartmentHead,
            {"user": department_head_user},
            {"department": program},
        )
        courses = [
            self._ensure(
                Course,
                {"code": "DEMO-PN101"},
                {
                    "title": "DEMO - Foundations of Mental Health",
                    "credit": 3,
                    "summary": "Fictional course for student lifecycle testing.",
                    "program": program,
                    "level": "Bachelor",
                    "year": 1,
                    "semester": "First",
                },
            ),
            self._ensure(
                Course,
                {"code": "DEMO-PN102"},
                {
                    "title": "DEMO - Therapeutic Communication",
                    "credit": 3,
                    "summary": "Fictional course for student lifecycle testing.",
                    "program": program,
                    "level": "Bachelor",
                    "year": 1,
                    "semester": "First",
                },
            ),
        ]
        offer = self._ensure(
            CourseOffer,
            {"dep_head": department_head, "semester": semester},
        )
        course_scores = (
            {
                "assignment": Decimal("8.60"),
                "mid_exam": Decimal("12.30"),
                "quiz": Decimal("9.00"),
                "attendance": Decimal("4.75"),
                "final_exam": Decimal("50.40"),
            },
            {
                "assignment": Decimal("7.50"),
                "mid_exam": Decimal("11.00"),
                "quiz": Decimal("8.00"),
                "attendance": Decimal("4.00"),
                "final_exam": Decimal("45.00"),
            },
        )
        for course, scores in zip(courses, course_scores):
            if not offer.courses.filter(pk=course.pk).exists():
                offer.courses.add(course)
                self.created_count += 1
            self._ensure(
                TakenCourse,
                {"student": student, "course": course, "semester": semester},
                scores,
            )
            self._ensure(
                AttendanceRecord,
                {
                    "student": student,
                    "course": course,
                    "remarks": "DEMO attendance record",
                },
                {"date": today - timedelta(days=1), "status": "present"},
            )
            self._ensure(
                ClassSession,
                {"course": course, "topic": "DEMO - Weekly learning session"},
                {"date": today - timedelta(days=1), "created_by": supervisor},
            )

        self._ensure(
            Result,
            {
                "student": student,
                "semester": "First",
                "session": session.session,
                "level": "Bachelor",
            },
            {"gpa": 3.75, "cgpa": 3.75},
        )
        assignment = self._ensure(
            CourseAssignment,
            {"course": courses[0], "title": "DEMO - Reflective practice"},
            {
                "description": "Fictional assessment for workflow demonstrations.",
                "assignment_type": "assignment",
                "max_score": Decimal("100.00"),
                "due_date": timezone.now() + timedelta(days=14),
                "created_by": supervisor,
                "is_published": True,
            },
        )
        self._ensure(
            AssignmentSubmission,
            {"assignment": assignment, "student": student},
            {
                "score": Decimal("88.00"),
                "feedback": "Demo submission reviewed successfully.",
                "graded_by": supervisor,
                "graded_at": timezone.now(),
            },
        )
        self._ensure(
            NewsAndEvents,
            {"title": "DEMO - Student Clinical Practice Orientation"},
            {
                "summary": "Fictional orientation event for dashboard demonstrations.",
                "posted_as": "Event",
                "event_date": today + timedelta(days=7),
                "semester": semester,
            },
        )

        ward = self._ensure(
            Ward,
            {"facility": "DEMO - Butabika Training Facility", "name": "DEMO - Ward A"},
            {
                "description": "Fictional ward for clinical placement demonstrations.",
                "capacity": 20,
                "is_active": True,
            },
        )
        placement = self._ensure(
            ClinicalPlacement,
            {"student": student, "ward": ward, "semester": semester},
            {
                "supervisor": supervisor,
                "starts_on": today - timedelta(days=7),
                "ends_on": today + timedelta(days=30),
                "status": ClinicalPlacement.Status.IN_PROGRESS,
                "learning_objectives": "DEMO: Therapeutic communication and patient safety.",
                "created_by": department_head_user,
            },
        )
        self._ensure(
            ClinicalLogEntry,
            {"placement": placement, "competency": "DEMO - Therapeutic communication"},
            {
                "date": today - timedelta(days=2),
                "shift": ClinicalLogEntry.Shift.DAY,
                "hours": Decimal("6.00"),
                "activity": "Completed a supervised fictional communication exercise.",
                "reflection": "Demo reflection for clinical log review.",
                "status": ClinicalLogEntry.Status.VERIFIED,
                "supervisor_feedback": "Demo entry verified.",
                "reviewed_at": timezone.now(),
                "reviewed_by": supervisor,
            },
        )

        fee_category = self._ensure(
            FeeCategory,
            {
                "name": "DEMO - Tuition",
                "semester": semester,
                "student": student,
            },
            {"description": "Fictional tuition fee.", "amount": Decimal("1200000.00")},
        )
        invoice = self._ensure(
            Invoice,
            {"student": student, "semester": semester},
            {
                "due_date": today + timedelta(days=30),
                "total_amount": Decimal("1200000.00"),
                "paid_amount": Decimal("300000.00"),
                "status": "partial",
            },
        )
        self._ensure(
            InvoiceItem,
            {"invoice": invoice, "category": fee_category},
            {"amount": Decimal("1200000.00")},
        )
        self._ensure(
            InvoicePayment,
            {"invoice": invoice, "reference": "DEMO-PAY-0001"},
            {
                "amount": Decimal("300000.00"),
                "payment_date": today,
                "method": InvoicePayment.Method.MOBILE_MONEY,
                "recorded_by": finance_user,
            },
        )

        self._seed_procurement(today)

    def _seed_procurement(self, today):
        procurement_user = self._demo_user(
            "demo_procurement",
            "demo.procurement@example.test",
            "Procurement Officer",
            is_procurement_officer=True,
        )
        procurement_department = self._ensure(
            ProcurementDepartment,
            {"name": "DEMO - Nursing Department"},
            {"slug": "demo-nursing-department"},
        )
        procurement_status = self._ensure(
            ProcurementStatus,
            {"name": "DEMO - Under Review"},
            {"slug": "demo-under-review", "is_default": False},
        )
        supplier_category = self._ensure(
            SupplierCategory,
            {"name": "DEMO - Clinical Supplies"},
            {"description": "Fictional supplier category."},
        )
        supplier = self._ensure(
            Supplier,
            {"name": "DEMO - Health Supplies Ltd"},
            {
                "category": supplier_category,
                "email": "demo.supplier@example.test",
                "phone": "+256700000104",
                "address": "Demo address - not a real supplier",
                "created_by": procurement_user,
            },
        )
        requisition = self._ensure(
            PurchaseRequisition,
            {"title": "DEMO - Ward training supplies"},
            {
                "description": "Fictional procurement request for print testing.",
                "department": procurement_department,
                "requested_by": procurement_user,
                "status": procurement_status,
                "total_amount": Decimal("850000.00"),
                "required_by": today + timedelta(days=21),
            },
        )
        purchase_order = self._ensure(
            PurchaseOrder,
            {"requisition": requisition},
            {
                "supplier": supplier,
                "total_amount": Decimal("850000.00"),
                "approved": False,
            },
        )
        self._ensure(
            PurchaseOrderItem,
            {
                "purchase_order": purchase_order,
                "description": "DEMO - Clinical practice supply kit",
            },
            {"quantity": 10, "unit_price": Decimal("85000.00")},
        )
        quotation = self._ensure(
            PurchaseQuotation,
            {"reference": "DEMO-QUOTE-0001"},
            {
                "supplier": supplier,
                "requisition": requisition,
                "date_received": today,
                "valid_until": today + timedelta(days=30),
                "status": PurchaseQuotation.Status.UNDER_REVIEW,
                "total_amount": Decimal("825000.00"),
                "notes": "Fictional supplier quotation for print testing.",
                "created_by": procurement_user,
            },
        )
        self._ensure(
            PurchaseQuotationItem,
            {
                "quotation": quotation,
                "description": "DEMO - Clinical practice supply kit",
            },
            {"quantity": 10, "unit_price": Decimal("82500.00")},
        )

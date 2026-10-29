from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import (
    Permission,
    Role,
    RolePermission,
    Student,
    User,
    UserPermission,
)
from audit.models import ActivityLog
from course.models import Program
from core.models import Semester, Session

from .models import ClinicalLogEntry, ClinicalPlacement, PlacementStatusHistory, Ward
from .services import review_log_entry, transition_placement


@override_settings(LANGUAGE_CODE="en")
class ClinicalTrainingTests(TestCase):
    def setUp(self):
        self.program = Program.objects.create(title="Psychiatric Nursing")
        self.session = Session.objects.create(session="2026/2027")
        self.semester = Semester.objects.create(
            semester="First",
            session=self.session,
            is_current_semester=True,
        )
        self.admin = User.objects.create_superuser(
            username="clinical-admin",
            email="clinical-admin@example.test",
            password="test-password",
        )
        self.supervisor = User.objects.create_user(
            username="clinical-supervisor",
            email="supervisor@example.test",
            password="test-password",
            is_lecturer=True,
            first_name="Sarah",
            last_name="Nurse",
        )
        self.student_user = User.objects.create_user(
            username="clinical-student",
            email="student@example.test",
            password="test-password",
            is_student=True,
            first_name="Amina",
            last_name="Kato",
        )
        self.student = Student.objects.create(
            student=self.student_user,
            program=self.program,
            level="Bachelor",
            year=1,
            registration_number="BSN-2026-101",
        )
        self.ward = Ward.objects.create(
            name="Acute Care",
            facility="Butabika Hospital",
            capacity=1,
        )
        self.placement = ClinicalPlacement.objects.create(
            student=self.student,
            ward=self.ward,
            semester=self.semester,
            supervisor=self.supervisor,
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 10, 30),
            created_by=self.admin,
        )
        self.placement_list_url = reverse("clinical:placement_list")
        self.placement_detail_url = reverse(
            "clinical:placement_detail",
            kwargs={"pk": self.placement.pk},
        )

    def test_students_only_see_their_own_placements(self):
        other_user = User.objects.create_user(
            username="other-clinical-student",
            password="test-password",
            is_student=True,
        )
        other_student = Student.objects.create(
            student=other_user,
            program=self.program,
            level="Bachelor",
            year=1,
            registration_number="BSN-2026-102",
        )
        ClinicalPlacement.objects.create(
            student=other_student,
            ward=self.ward,
            semester=self.semester,
            supervisor=self.supervisor,
            starts_on=date(2026, 11, 1),
            ends_on=date(2026, 11, 30),
        )
        self.client.force_login(self.student_user)

        response = self.client.get(self.placement_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.placement.pk)
        self.assertNotContains(response, "BSN-2026-102")

    def test_placement_creation_rejects_overlapping_student_and_full_ward(self):
        another_user = User.objects.create_user(
            username="another-clinical-student",
            password="test-password",
            is_student=True,
        )
        another_student = Student.objects.create(
            student=another_user,
            program=self.program,
            level="Bachelor",
            year=1,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("clinical:placement_create"),
            {
                "student": another_student.pk,
                "ward": self.ward.pk,
                "semester": self.semester.pk,
                "supervisor": self.supervisor.pk,
                "starts_on": "2026-10-10",
                "ends_on": "2026-10-20",
                "learning_objectives": "Practice therapeutic communication",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no available placement capacity")
        self.assertEqual(ClinicalPlacement.objects.count(), 1)

    def test_placement_status_transition_records_history_and_audit(self):
        transition_placement(
            self.placement.pk,
            ClinicalPlacement.Status.IN_PROGRESS,
            self.admin,
            "Student began rotation",
        )

        self.placement.refresh_from_db()
        history = PlacementStatusHistory.objects.get(placement=self.placement)
        self.assertEqual(self.placement.status, ClinicalPlacement.Status.IN_PROGRESS)
        self.assertEqual(history.from_status, ClinicalPlacement.Status.PLANNED)
        self.assertEqual(history.to_status, ClinicalPlacement.Status.IN_PROGRESS)
        self.assertEqual(history.changed_by, self.admin)
        self.assertEqual(
            ActivityLog.objects.filter(target_model="clinical.ClinicalPlacement").count(),
            1,
        )

    def test_terminal_placement_cannot_be_reopened(self):
        self.placement.status = ClinicalPlacement.Status.COMPLETED
        self.placement.save(update_fields=("status",))

        with self.assertRaises(ValidationError):
            transition_placement(
                self.placement.pk,
                ClinicalPlacement.Status.IN_PROGRESS,
                self.admin,
            )

    def test_student_submits_log_and_supervisor_verifies_hours(self):
        self.placement.status = ClinicalPlacement.Status.IN_PROGRESS
        self.placement.save(update_fields=("status",))
        self.client.force_login(self.student_user)
        response = self.client.post(
            self.placement_detail_url,
            {
                "date": "2026-10-18",
                "shift": ClinicalLogEntry.Shift.DAY,
                "hours": "8.00",
                "competency": "Mental status examination",
                "activity": "Completed an assessment with supervisor present.",
                "reflection": "Used open-ended questions.",
            },
        )

        self.assertEqual(response.status_code, 302)
        entry = ClinicalLogEntry.objects.get(placement=self.placement)
        self.assertEqual(entry.status, ClinicalLogEntry.Status.PENDING)

        review_permission = Permission.objects.get(
            module="clinical",
            action="verify_log_entries",
        )
        supervisor_role = Role.objects.create(
            name="Clinical Supervisor",
            slug="clinical-supervisor",
        )
        RolePermission.objects.create(
            role=supervisor_role,
            permission=review_permission,
        )
        self.supervisor.role = supervisor_role
        self.supervisor.save(update_fields=("role",))
        review_log_entry(
            entry.pk,
            ClinicalLogEntry.Status.VERIFIED,
            self.supervisor,
            "Competency demonstrated.",
        )

        entry.refresh_from_db()
        self.assertEqual(entry.status, ClinicalLogEntry.Status.VERIFIED)
        self.assertEqual(entry.reviewed_by, self.supervisor)
        self.assertEqual(entry.hours, Decimal("8.00"))
        self.assertIsNotNone(entry.reviewed_at)

    def test_student_cannot_submit_logs_outside_placement_dates(self):
        self.placement.status = ClinicalPlacement.Status.IN_PROGRESS
        self.placement.save(update_fields=("status",))
        self.client.force_login(self.student_user)

        response = self.client.post(
            self.placement_detail_url,
            {
                "date": "2026-11-01",
                "shift": ClinicalLogEntry.Shift.DAY,
                "hours": "8.00",
                "competency": "Mental status examination",
                "activity": "Completed an assessment.",
                "reflection": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClinicalLogEntry.objects.exists())

    def test_role_permission_can_manage_placements_and_explicit_deny_wins(self):
        user = User.objects.create_user(
            username="clinical-coordinator",
            password="test-password",
        )
        manage_permission = Permission.objects.get(
            module="clinical",
            action="manage_placements",
        )
        role = Role.objects.create(
            name="Clinical Coordinator",
            slug="clinical-coordinator",
        )
        RolePermission.objects.create(role=role, permission=manage_permission)
        user.role = role
        user.save(update_fields=("role",))
        self.client.force_login(user)

        allowed_response = self.client.get(
            reverse("clinical:ward_list")
        )
        UserPermission.objects.create(
            user=user,
            permission=manage_permission,
            effect=UserPermission.DENY,
        )
        denied_response = self.client.get(reverse("clinical:ward_list"))

        self.assertEqual(allowed_response.status_code, 200)
        self.assertEqual(denied_response.status_code, 403)

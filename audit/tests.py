from django.test import RequestFactory, TestCase

from accounts.models import User
from audit.models import ActivityLog
from audit.utils import log_activity


class ActivityLogTests(TestCase):
    def test_log_activity_records_actor_request_and_object_changes(self):
        user = User.objects.create_user(username="audited-user", password="test-password")
        request = RequestFactory().post("/")
        request.META["REMOTE_ADDR"] = "192.0.2.10"
        request.META["HTTP_USER_AGENT"] = "Audit test"

        entry = log_activity(
            user,
            "student.updated",
            "Updated student profile",
            request=request,
            instance=user,
            before={"email": "old@example.test"},
            after={"email": "new@example.test"},
        )

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(entry.user, user)
        self.assertEqual(entry.ip_address, "192.0.2.10")
        self.assertEqual(entry.user_agent, "Audit test")
        self.assertEqual(entry.target_model, "accounts.User")
        self.assertEqual(entry.object_id, str(user.pk))
        self.assertEqual(entry.before, {"email": "old@example.test"})
        self.assertEqual(entry.after, {"email": "new@example.test"})

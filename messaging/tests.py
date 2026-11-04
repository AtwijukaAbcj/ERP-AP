from django.forms import CheckboxSelectMultiple
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from .forms import ComposeMessageForm
from .models import Conversation, Message, MessageDelivery, UserNotification


@override_settings(LANGUAGE_CODE="en")
class MessagingWorkflowTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="message-sender",
            email="sender@example.test",
            password="test-password",
            is_lecturer=True,
        )
        self.recipient = User.objects.create_user(
            username="message-recipient",
            email="recipient@example.test",
            password="test-password",
            is_student=True,
        )

    def test_direct_message_creates_unread_notification_and_reply(self):
        self.client.force_login(self.sender)
        response = self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "individual",
                "users": [self.recipient.pk],
                "subject": "Course update",
                "body": "Please review the new course schedule.",
            },
        )

        conversation = Conversation.objects.get()
        self.assertRedirects(
            response,
            reverse("messaging:conversation", args=(conversation.pk,)),
            fetch_redirect_response=False,
        )
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 1)
        self.assertEqual(
            MessageDelivery.objects.filter(
                recipient=self.recipient,
                read_at__isnull=True,
            ).count(),
            1,
        )

        self.client.force_login(self.recipient)
        inbox_response = self.client.get(reverse("messaging:inbox"))
        self.assertContains(inbox_response, "1 unread")
        self.assertContains(inbox_response, "fa-envelope")
        self.assertEqual(inbox_response.context["unread_message_count"], 1)
        self.assertEqual(inbox_response.context["unread_notification_count"], 1)
        self.assertContains(inbox_response, reverse("messaging:notifications"))
        self.assertContains(inbox_response, reverse("messaging:inbox"))

        notification_response = self.client.get(
            reverse("messaging:notifications")
        )
        notification = UserNotification.objects.get(recipient=self.recipient)
        self.assertContains(notification_response, "Course update")
        self.assertContains(
            notification_response,
            reverse("messaging:open_notification", args=(notification.pk,)),
        )

        thread_response = self.client.get(
            reverse("messaging:conversation", args=(conversation.pk,))
        )
        self.assertContains(thread_response, "Please review the new course schedule.")
        self.assertIsNotNone(
            MessageDelivery.objects.get(recipient=self.recipient).read_at
        )

        reply_response = self.client.post(
            reverse("messaging:conversation", args=(conversation.pk,)),
            {"body": "I have reviewed it."},
        )
        self.assertRedirects(
            reply_response,
            reverse("messaging:conversation", args=(conversation.pk,)),
        )
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)
        self.assertTrue(
            MessageDelivery.objects.filter(
                recipient=self.sender,
                read_at__isnull=True,
            ).exists()
        )

    def test_opening_notification_marks_alert_read_and_links_to_conversation(self):
        self.client.force_login(self.sender)
        self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "individual",
                "users": [self.recipient.pk],
                "subject": "Notification test",
                "body": "This creates a separate notification.",
            },
        )
        conversation = Conversation.objects.get()
        notification = UserNotification.objects.get(recipient=self.recipient)
        self.client.force_login(self.recipient)

        response = self.client.get(
            reverse("messaging:open_notification", args=(notification.pk,))
        )

        self.assertRedirects(
            response,
            reverse("messaging:conversation", args=(conversation.pk,)),
            fetch_redirect_response=False,
        )
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertIsNone(
            MessageDelivery.objects.get(recipient=self.recipient).read_at
        )

    def test_staff_can_send_to_an_account_category(self):
        second_student = User.objects.create_user(
            username="second-student",
            email="second-student@example.test",
            password="test-password",
            is_student=True,
        )
        self.client.force_login(self.sender)

        response = self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "category",
                "categories": ["is_student"],
                "subject": "Student announcement",
                "body": "Registration opens tomorrow.",
            },
        )

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get()
        self.assertTrue(conversation.is_group)
        self.assertSetEqual(
            set(conversation.participants.values_list("pk", flat=True)),
            {self.sender.pk, self.recipient.pk, second_student.pk},
        )
        self.assertEqual(
            MessageDelivery.objects.filter(message__conversation=conversation).count(),
            2,
        )

    def test_staff_can_send_to_a_custom_role(self):
        role = Role.objects.create(name="Academic Advisers", slug="academic-advisers")
        second_role = Role.objects.create(
            name="Program Coordinators",
            slug="program-coordinators",
        )
        role_user = User.objects.create_user(
            username="role-recipient",
            email="role-recipient@example.test",
            password="test-password",
        )
        second_role_user = User.objects.create_user(username="second-role-recipient")
        role.users.add(role_user)
        second_role.users.add(second_role_user)
        form = ComposeMessageForm(self.sender)
        self.assertIsInstance(form.fields["roles"].widget, CheckboxSelectMultiple)
        self.client.force_login(self.sender)
        compose_response = self.client.get(reverse("messaging:compose"))
        self.assertContains(compose_response, 'name="roles"')
        self.assertContains(compose_response, 'type="checkbox"')
        self.assertContains(compose_response, "Search roles...")
        self.assertContains(compose_response, "Select visible")

        response = self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "role",
                "roles": [role.pk, second_role.pk],
                "subject": "Adviser briefing",
                "body": "Please attend the briefing.",
            },
        )

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get()
        self.assertSetEqual(
            set(
                conversation.participants.exclude(pk=self.sender.pk).values_list(
                    "pk", flat=True
                )
            ),
            {role_user.pk, second_role_user.pk},
        )
        self.assertSetEqual(
            set(UserNotification.objects.values_list("recipient_id", flat=True)),
            {role_user.pk, second_role_user.pk},
        )

    def test_non_staff_cannot_send_group_messages(self):
        self.sender.is_lecturer = False
        self.sender.save(update_fields=("is_lecturer",))
        self.client.force_login(self.recipient)

        response = self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "category",
                "categories": ["is_lecturer"],
                "subject": "Announcement",
                "body": "This should not be sent.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Conversation.objects.exists())

    def test_non_participant_cannot_open_conversation(self):
        self.client.force_login(self.sender)
        self.client.post(
            reverse("messaging:compose"),
            {
                "recipient_type": "individual",
                "users": [self.recipient.pk],
                "subject": "Private",
                "body": "Private content",
            },
        )
        conversation = Conversation.objects.get()
        outsider = User.objects.create_user(
            username="conversation-outsider",
            email="outsider@example.test",
            password="test-password",
        )
        self.client.force_login(outsider)

        response = self.client.get(
            reverse("messaging:conversation", args=(conversation.pk,))
        )

        self.assertEqual(response.status_code, 404)

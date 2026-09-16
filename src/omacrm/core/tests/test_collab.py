import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import Attachment, Note, Notification, User
from omacrm.core.services import stream


class StreamServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author2", "author2@example.com", "pw")
        self.mentioned = User.objects.create_user("mentioned", "m@example.com", "pw")
        from omacrm.crm.models import Account

        self.account = Account.objects.create(name="Stream Co")

    def test_post_note_creates_note_and_mention_notification(self):
        note = stream.post_note(
            self.account,
            "Hello @mentioned and @nobody",
            user=self.author,
            is_internal=True,
        )
        self.assertEqual(note.type, Note.Type.POST)
        self.assertEqual(note.created_by, self.author)
        self.assertTrue(note.is_internal)

        notification = Notification.objects.filter(
            user=self.mentioned, type=Notification.Type.MENTION
        )
        self.assertEqual(notification.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_post_note_does_not_notify_author(self):
        stream.post_note(self.account, "Self @author2", user=self.author)
        self.assertFalse(Notification.objects.filter(user=self.author).exists())

    def test_dashboard_unread_kpi_is_user_scoped(self):
        from omacrm.core.admin.dashboard import dashboard_callback

        Notification.objects.create(user=self.author, type=Notification.Type.SYSTEM)
        Notification.objects.create(
            user=self.author, type=Notification.Type.SYSTEM, read=True
        )
        other = User.objects.create_user("other-kpi", "other@example.com", "pw")
        Notification.objects.create(user=other, type=Notification.Type.SYSTEM)

        context = dashboard_callback(
            type("Request", (), {"user": self.author})(), {}
        )
        unread = next(
            kpi for kpi in context["kpis"] if kpi["label"] == "Unread notifications"
        )
        self.assertEqual(unread["value"], 1)


class NotificationAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("notif-admin", "na@example.com", "pw")
        self.client.force_login(self.admin)

    def test_mark_as_read_action(self):
        notification = Notification.objects.create(
            user=self.admin, type=Notification.Type.SYSTEM
        )
        response = self.client.post(
            reverse("admin:core_notification_changelist"),
            {
                "action": "mark_as_read",
                "_selected_action": [notification.pk],
                "index": "0",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.read)

    def test_sidebar_calendar_link_present(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, reverse("crm_calendar"))


class AttachmentTests(TestCase):
    def test_attachment_metadata_populated(self):
        from omacrm.crm.models import Account

        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            account = Account.objects.create(name="Attachment Co")
            attachment = Attachment.objects.create(
                file=SimpleUploadedFile(
                    "note.txt", b"hello world", content_type="text/plain"
                ),
                related=account,
            )
            self.assertEqual(attachment.name, "note.txt")
            self.assertEqual(attachment.size, 11)
            self.assertEqual(attachment.mime_type, "text/plain")

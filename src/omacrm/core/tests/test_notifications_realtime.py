import json

from django.contrib.staticfiles import finders
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import Notification, Preferences, User
from omacrm.core.services.jobs import JobRunner, schedule


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "digest", "digest@example.com", "pw"
        )

    def test_digest_is_sent_and_marked_processed(self):
        notification = Notification.objects.create(
            user=self.user, type=Notification.Type.SYSTEM, message="Task assigned"
        )
        schedule("core.send_notification_emails")
        JobRunner.run_pending()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Task assigned", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["digest@example.com"])
        notification.refresh_from_db()
        self.assertTrue(notification.email_is_processed)

    def test_users_without_email_are_skipped(self):
        user = User.objects.create_user("no-mail", "", "pw")
        notification = Notification.objects.create(
            user=user, type=Notification.Type.SYSTEM, message="No address"
        )
        schedule("core.send_notification_emails")
        JobRunner.run_pending()

        self.assertEqual(len(mail.outbox), 0)
        notification.refresh_from_db()
        self.assertTrue(notification.email_is_processed)

    def test_per_user_opt_out(self):
        Preferences.objects.create(user=self.user, notifications_config={"email": False})
        notification = Notification.objects.create(
            user=self.user, type=Notification.Type.SYSTEM, message="Muted"
        )
        schedule("core.send_notification_emails")
        JobRunner.run_pending()

        self.assertEqual(len(mail.outbox), 0)
        notification.refresh_from_db()
        self.assertTrue(notification.email_is_processed)

    def test_global_toggle_disables_sending(self):
        from constance import config

        config.notification_email_enabled = False
        try:
            notification = Notification.objects.create(
                user=self.user, type=Notification.Type.SYSTEM, message="Global off"
            )
            schedule("core.send_notification_emails")
            JobRunner.run_pending()

            self.assertEqual(len(mail.outbox), 0)
            notification.refresh_from_db()
            self.assertFalse(notification.email_is_processed)
        finally:
            config.notification_email_enabled = True


class NotificationStreamTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("sse", "sse@example.com", "pw")
        self.client.force_login(self.admin)

    def test_stream_emits_init_event(self):
        Notification.objects.create(
            user=self.admin, type=Notification.Type.SYSTEM, message="Ping"
        )
        response = self.client.get(reverse("notification_stream"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))

        first_chunk = next(iter(response.streaming_content)).decode()
        self.assertTrue(first_chunk.startswith("data: "))
        payload = json.loads(first_chunk[len("data: "):])
        self.assertEqual(payload["type"], "init")
        self.assertEqual(payload["count"], 1)
        response.close()

    def test_stream_requires_staff(self):
        self.client.force_login(
            User.objects.create_user("plain", "plain@example.com", "pw")
        )
        response = self.client.get(reverse("notification_stream"))
        self.assertEqual(response.status_code, 302)

    def test_admin_pages_load_live_notifications_script(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "/static/core/js/notifications.js")

    def test_static_asset_exists(self):
        self.assertIsNotNone(finders.find("core/js/notifications.js"))

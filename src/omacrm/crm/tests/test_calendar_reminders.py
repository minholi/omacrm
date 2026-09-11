from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from omacrm.core.models import Note, Notification, User
from omacrm.core.services.jobs import JobRunner, schedule
from omacrm.crm.models import Account, Call, Meeting, Reminder, Task
from omacrm.crm.services.reminders import sync_reminders


class CalendarViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("cal-admin", "cal@example.com", "pw")
        self.client.force_login(self.admin)
        moment = timezone.now().replace(minute=0, second=0, microsecond=0)
        self.call = Call.objects.create(
            name="Calendar Call",
            date_start=moment + timedelta(hours=1),
            assigned_user=self.admin,
        )
        self.other = User.objects.create_user("cal-other", "other@example.com", "pw")
        Call.objects.create(
            name="Foreign Call",
            date_start=moment + timedelta(hours=2),
            assigned_user=self.other,
        )

    def test_calendar_renders_my_events(self):
        response = self.client.get(reverse("crm_calendar"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calendar Call")
        self.assertNotContains(response, "Foreign Call")

    def test_calendar_all_events(self):
        response = self.client.get(reverse("crm_calendar"), {"assigned": "all"})
        self.assertContains(response, "Foreign Call")

    def test_calendar_requires_staff(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("crm_calendar"))
        self.assertEqual(response.status_code, 302)


class ReminderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("rem-admin", "rem@example.com", "pw")

    def test_sync_reminders_creates_and_replaces(self):
        start = timezone.now() + timedelta(days=1)
        call = Call.objects.create(
            name="Reminder Call",
            date_start=start,
            assigned_user=self.admin,
            reminders=[{"seconds": 300, "type": "Popup"}],
        )
        call_ct = ContentType.objects.get_for_model(Call)
        reminder = Reminder.objects.get(entity_type=call_ct, entity_id=call.pk)
        expected = start - timedelta(seconds=300)
        self.assertLess(abs((reminder.remind_at - expected).total_seconds()), 2)
        self.assertEqual(reminder.user, self.admin)

        call.reminders = []
        call.save()
        self.assertFalse(
            Reminder.objects.filter(entity_type=call_ct, entity_id=call.pk).exists()
        )

    def test_send_due_reminders_job(self):
        task = Task.objects.create(name="Due Task", assigned_user=self.admin)
        Reminder.objects.create(
            remind_at=timezone.now() - timedelta(minutes=1),
            user=self.admin,
            entity=task,
        )
        schedule("crm.send_reminders")
        JobRunner.run_pending()

        self.assertTrue(
            Notification.objects.filter(
                user=self.admin, message__contains="Due Task"
            ).exists()
        )
        task_ct = ContentType.objects.get_for_model(Task)
        self.assertTrue(
            Reminder.objects.get(entity_type=task_ct, entity_id=task.pk).is_submitted
        )

    def test_meeting_and_task_generate_reminders(self):
        moment = timezone.now() + timedelta(hours=2)
        meeting = Meeting.objects.create(
            name="Reminder Meeting",
            date_start=moment,
            assigned_user=self.admin,
            reminders=[{"seconds": 600, "type": "Email"}],
        )
        meeting_ct = ContentType.objects.get_for_model(Meeting)
        self.assertEqual(
            Reminder.objects.filter(
                entity_type=meeting_ct, entity_id=meeting.pk
            ).count(),
            1,
        )
        task = Task.objects.create(
            name="Reminder Task",
            date_end=moment,
            assigned_user=self.admin,
            reminders=[{"seconds": 0, "type": "Popup"}],
        )
        task_ct = ContentType.objects.get_for_model(Task)
        self.assertEqual(
            Reminder.objects.filter(entity_type=task_ct, entity_id=task.pk).count(),
            1,
        )


class StreamAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("stream-admin", "sa@example.com", "pw")
        self.client.force_login(self.admin)
        self.account = Account.objects.create(name="Stream Account")

    def test_stream_dataset_rendered(self):
        response = self.client.get(
            reverse("admin:crm_account_change", args=[self.account.pk])
        )
        self.assertContains(response, "Stream")

    def test_post_note_action(self):
        response = self.client.post(
            f"/admin/crm/account/{self.account.pk}/add_note/",
            {"_form_submitted": "on", "post": "Called the customer"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Note.objects.filter(
                parent_id=self.account.pk, type=Note.Type.POST, post="Called the customer"
            ).exists()
        )

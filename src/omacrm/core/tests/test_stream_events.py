from django.test import TestCase

from omacrm.core.admin.views import _pending_stream_events
from omacrm.core.models import StreamEvent, User
from omacrm.core.services.context import set_current_user
from omacrm.crm.models import Account


class StreamEventTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@example.com", "pw")
        self.other = User.objects.create_user("other", "other@example.com", "pw")
        self.account = Account.objects.create(
            name="Live Co", assigned_user=self.owner
        )
        StreamEvent.objects.all().delete()

    def _change_as(self, user):
        set_current_user(user)
        try:
            self.account.description = f"changed by {user.user_name}"
            self.account.save()
        finally:
            set_current_user(None)

    def test_change_by_someone_else_notifies_assignee(self):
        self._change_as(self.other)

        event = StreamEvent.objects.filter(user=self.owner).first()
        self.assertIsNotNone(event)
        self.assertIn("Live Co", event.message)
        self.assertIn("Update", event.message)
        self.assertFalse(StreamEvent.objects.filter(user=self.other).exists())

    def test_assignee_does_not_get_own_event(self):
        self._change_as(self.owner)
        self.assertFalse(StreamEvent.objects.filter(user=self.owner).exists())

    def test_created_record_notifies_assignee(self):
        set_current_user(self.other)
        try:
            Account.objects.create(name="Fresh Co", assigned_user=self.owner)
        finally:
            set_current_user(None)

        event = StreamEvent.objects.filter(user=self.owner).first()
        self.assertIsNotNone(event)
        self.assertIn("Create", event.message)

    def test_unassigned_record_emits_nothing(self):
        set_current_user(self.other)
        try:
            Account.objects.create(name="Nobody Co")
        finally:
            set_current_user(None)
        self.assertFalse(StreamEvent.objects.exists())

    def test_pending_stream_events_helper(self):
        self._change_as(self.other)
        event = StreamEvent.objects.get(user=self.owner)

        self.assertEqual(
            [item["message"] for item in _pending_stream_events(self.owner, 0)],
            [event.message],
        )
        self.assertEqual(_pending_stream_events(self.owner, event.pk), [])
        self.assertEqual(_pending_stream_events(self.other, 0), [])

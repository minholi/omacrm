from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import Note, User, UserReaction
from omacrm.core.services.reactions import toggle_reaction


class ReactionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("react", "react@example.com", "pw")
        self.note = Note.objects.create(type=Note.Type.POST, post="Hello")

    def test_toggle_adds_and_removes(self):
        self.assertTrue(toggle_reaction(self.note, self.user, "👍"))
        self.assertEqual(UserReaction.objects.count(), 1)
        self.assertFalse(toggle_reaction(self.note, self.user, "👍"))
        self.assertEqual(UserReaction.objects.count(), 0)

    def test_summary_groups_emojis(self):
        other = User.objects.create_user("react2", "react2@example.com", "pw")
        toggle_reaction(self.note, self.user, "👍")
        toggle_reaction(self.note, other, "👍")
        toggle_reaction(self.note, self.user, "❤️")

        summary = self.note.reaction_summary
        self.assertIn("👍 2", summary)
        self.assertIn("❤️ 1", summary)

    def test_different_emojis_are_separate(self):
        toggle_reaction(self.note, self.user, "👍")
        self.assertTrue(toggle_reaction(self.note, self.user, "🎉"))
        self.assertEqual(
            UserReaction.objects.filter(note=self.note, user=self.user).count(), 2
        )


class ReactionAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("react-admin", "ra@example.com", "pw")
        self.client.force_login(self.admin)
        self.note = Note.objects.create(type=Note.Type.POST, post="Hello")

    def _react(self, emoji="👍"):
        return self.client.post(
            f"/admin/core/note/{self.note.pk}/react/",
            {"_form_submitted": "on", "emoji": emoji},
        )

    def test_row_action_toggles_reaction(self):
        response = self._react()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserReaction.objects.filter(
                note=self.note, user=self.admin, emoji="👍"
            ).exists()
        )

        self._react()
        self.assertFalse(
            UserReaction.objects.filter(note=self.note, user=self.admin).exists()
        )

    def test_changelist_shows_reaction_summary(self):
        toggle_reaction(self.note, self.admin, "👍")
        response = self.client.get(reverse("admin:core_note_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "👍 1")

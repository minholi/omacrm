"""Independent verification of stars/following — written by the orchestrator.

Hypotheses the delegated work did not have to satisfy: a follower gets exactly
one notification per post (and one per post when there are two), the changelist
query count does not grow with the number of rows, the toggle refuses a record
of an entity that has stars disabled, and unfollowing actually silences.
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from omacrm.core.models import (
    Notification,
    Preferences,
    StreamSubscription,
    User,
)
from omacrm.core.services import stream, subscriptions
from omacrm.crm.models import Account


class SubscriptionSemanticsTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("sem-author", "author@example.com", "pw")
        self.follower = User.objects.create_user("sem-follower", "f@example.com", "pw")
        self.account = Account.objects.create(name="Semantics Co")

    def _notifications(self, user, kind="Stream"):
        return Notification.objects.filter(user=user, type=kind).count()

    # -- notification fan-out ------------------------------------------------

    def test_follower_gets_exactly_one_notification_per_post(self):
        subscriptions.set_following(self.follower, self.account, True)
        stream.post_note(self.account, "first post", user=self.author)
        self.assertEqual(self._notifications(self.follower), 1)
        # a second post is a second notification, not a duplicate of the first
        stream.post_note(self.account, "second post", user=self.author)
        self.assertEqual(self._notifications(self.follower), 2)

    def test_mention_plus_follow_does_not_explode(self):
        subscriptions.set_following(self.follower, self.account, True)
        mention = f"@{self.follower.user_name}"
        self.assertRegex(mention, stream.MENTION_RE, "mention format changed")
        stream.post_note(self.account, f"hello {mention}", user=self.author)
        total = Notification.objects.filter(user=self.follower).count()
        kinds = sorted(
            Notification.objects.filter(user=self.follower).values_list(
                "type", flat=True
            )
        )
        print(f"\n  mention+follow -> {total} notification(s): {kinds}")
        self.assertLessEqual(total, 2, f"a single post produced {total} notifications")

    def test_unfollowing_silences_further_posts(self):
        subscriptions.set_following(self.follower, self.account, True)
        stream.post_note(self.account, "while followed", user=self.author)
        self.assertEqual(self._notifications(self.follower), 1)
        subscriptions.set_following(self.follower, self.account, False)
        stream.post_note(self.account, "after unfollow", user=self.author)
        self.assertEqual(self._notifications(self.follower), 1)

    def test_author_who_also_follows_is_not_notified_of_their_own_post(self):
        subscriptions.set_following(self.author, self.account, True)
        stream.post_note(self.account, "mine", user=self.author)
        self.assertEqual(self._notifications(self.author), 0)

    # -- list view must not be N+1 ------------------------------------------

    def test_changelist_query_count_does_not_grow_with_rows(self):
        admin = User.objects.create_superuser("sem-admin", "admin@example.com", "pw")
        self.client.force_login(admin)
        url = reverse("admin:crm_account_changelist")

        for index in range(3):
            Account.objects.create(name=f"Row three {index}")
        with CaptureQueriesContext(connection) as few:
            self.client.get(url)
        for index in range(10):
            Account.objects.create(name=f"Row twelve {index}")
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)

        print(
            f"\n  changelist queries: 4 rows -> {len(few)} | 14 rows -> {len(many)}"
        )
        # A true N+1 would add ~10 queries for the 10 extra rows. The count must
        # stay flat; a small variation from unrelated per-render queries is fine.
        self.assertLessEqual(
            len(many),
            len(few) + 2,
            f"query count grew with the number of rows ({len(few)} -> {len(many)}) "
            "— the star annotation looks N+1",
        )

    # -- the toggle endpoint guards -----------------------------------------

    def test_toggle_rejects_an_entity_without_stars(self):
        from omacrm.core.models import Team

        admin = User.objects.create_superuser("sem-admin2", "admin2@example.com", "pw")
        self.client.force_login(admin)
        team = Team.objects.create(name="No stars here")
        url = reverse(
            "admin:core_team_subscription_toggle", args=["star", team.pk]
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400, response.content)

    def test_toggle_rejects_an_unknown_kind(self):
        admin = User.objects.create_superuser("sem-admin3", "admin3@example.com", "pw")
        self.client.force_login(admin)
        url = reverse(
            "admin:crm_account_subscription_toggle", args=["nonsense", self.account.pk]
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400, response.content)

    def test_toggle_returns_404_for_a_missing_record(self):
        admin = User.objects.create_superuser("sem-admin4", "admin4@example.com", "pw")
        self.client.force_login(admin)
        url = reverse(
            "admin:crm_account_subscription_toggle", args=["star", 999999]
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404, response.content)

    # -- auto-follow must not accumulate duplicates -------------------------

    def test_auto_follow_does_not_duplicate_across_create_and_note(self):
        Preferences.objects.create(
            user=self.author, auto_follow_entity_types=["Account"]
        )
        # creating the record follows it, posting on it follows it again
        subscriptions.auto_follow_created(self.account)
        stream.post_note(self.account, "posting on my own record", user=self.author)
        self.assertEqual(
            StreamSubscription.objects.filter(
                user=self.author, entity_type="Account", entity_id=self.account.pk
            ).count(),
            1,
        )

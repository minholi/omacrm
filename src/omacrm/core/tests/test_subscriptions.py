from django.test import TestCase
from django.urls import reverse

from omacrm.core.metadata.registry import registry
from omacrm.core.models import (
    CustomEntity,
    DynamicRecord,
    Notification,
    Preferences,
    StarSubscription,
    StreamSubscription,
    User,
)
from omacrm.core.services import custom_entities, reactions, stream, subscriptions
from omacrm.crm.models import Account, Contact, Task


class StarServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("star-user", "star@example.com", "pw")
        self.other = User.objects.create_user("star-other", "other@example.com", "pw")
        self.account = Account.objects.create(name="Acme")

    def test_star_unstar_is_idempotent(self):
        self.assertFalse(subscriptions.is_starred(self.user, self.account))

        self.assertTrue(subscriptions.set_starred(self.user, self.account, True))
        self.assertTrue(subscriptions.set_starred(self.user, self.account, True))
        self.assertEqual(StarSubscription.objects.count(), 1)
        self.assertTrue(subscriptions.is_starred(self.user, self.account))

        self.assertFalse(subscriptions.set_starred(self.user, self.account, False))
        self.assertFalse(subscriptions.set_starred(self.user, self.account, False))
        self.assertEqual(StarSubscription.objects.count(), 0)
        self.assertFalse(subscriptions.is_starred(self.user, self.account))

    def test_stars_are_per_user(self):
        subscriptions.set_starred(self.user, self.account, True)
        self.assertTrue(subscriptions.is_starred(self.user, self.account))
        self.assertFalse(subscriptions.is_starred(self.other, self.account))

    def test_stars_are_per_entity_type(self):
        contact = Contact.objects.create(first_name="Ann", last_name="Lee")
        subscriptions.set_starred(self.user, self.account, True)

        self.assertTrue(subscriptions.is_starred(self.user, self.account))
        self.assertFalse(subscriptions.is_starred(self.user, contact))

    def test_unauthenticated_user_cannot_star(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(subscriptions.set_starred(AnonymousUser(), self.account, True))
        self.assertEqual(StarSubscription.objects.count(), 0)


class FollowingServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("follow-user", "follow@example.com", "pw")
        self.account = Account.objects.create(name="Acme")

    def test_follow_unfollow_is_idempotent(self):
        self.assertFalse(subscriptions.is_following(self.user, self.account))

        self.assertTrue(subscriptions.set_following(self.user, self.account, True))
        self.assertTrue(subscriptions.set_following(self.user, self.account, True))
        self.assertEqual(StreamSubscription.objects.count(), 1)

        self.assertFalse(subscriptions.set_following(self.user, self.account, False))
        self.assertFalse(subscriptions.set_following(self.user, self.account, False))
        self.assertEqual(StreamSubscription.objects.count(), 0)

    def test_following_is_per_user_and_record(self):
        other_user = User.objects.create_user("follow-other", "fo@example.com", "pw")
        other_account = Account.objects.create(name="Globex")

        subscriptions.set_following(self.user, self.account, True)
        self.assertTrue(subscriptions.is_following(self.user, self.account))
        self.assertFalse(subscriptions.is_following(other_user, self.account))
        self.assertFalse(subscriptions.is_following(self.user, other_account))

    def test_following_requires_stream_enabled_entity(self):
        preferences = Preferences.objects.create(user=self.user)
        self.assertFalse(subscriptions.set_following(self.user, preferences, True))
        self.assertEqual(StreamSubscription.objects.count(), 0)

    def test_followers_of_excludes_inactive_users(self):
        active = User.objects.create_user("f-active", "fa@example.com", "pw")
        inactive = User.objects.create_user(
            "f-inactive", "fi@example.com", "pw", is_active=False
        )
        subscriptions.set_following(active, self.account, True)
        subscriptions.set_following(inactive, self.account, True)

        self.assertEqual(list(subscriptions.followers_of(self.account)), [active])


class AnnotationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ann-user", "ann@example.com", "pw")

    def test_starred_annotation_is_one_query(self):
        for index in range(3):
            Account.objects.create(name=f"Co {index}")
        subscriptions.set_starred(self.user, Account.objects.first(), True)

        with self.assertNumQueries(1):
            rows = list(
                subscriptions.annotate_starred(
                    Account.objects.order_by("pk"), self.user, "Account"
                )
            )
        self.assertEqual([row.starred for row in rows], [True, False, False])

    def test_followed_annotation_is_one_query(self):
        for index in range(3):
            Account.objects.create(name=f"Co {index}")
        subscriptions.set_following(self.user, Account.objects.last(), True)

        with self.assertNumQueries(1):
            rows = list(
                subscriptions.annotate_followed(
                    Account.objects.order_by("pk"), self.user, "Account"
                )
            )
        self.assertEqual([row.followed for row in rows], [False, False, True])


class AutoFollowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("auto-user", "auto@example.com", "pw")
        self.other = User.objects.create_user("auto-other", "ao@example.com", "pw")

    def test_create_fans_out_to_users_with_the_preference(self):
        Preferences.objects.create(
            user=self.user, auto_follow_entity_types=["Account"]
        )
        account = Account.objects.create(name="Auto Co")

        self.assertTrue(subscriptions.is_following(self.user, account))
        self.assertFalse(subscriptions.is_following(self.other, account))

    def test_create_ignores_types_not_in_the_preference(self):
        Preferences.objects.create(
            user=self.user, auto_follow_entity_types=["Opportunity"]
        )
        account = Account.objects.create(name="Plain Co")

        self.assertFalse(subscriptions.is_following(self.user, account))

    def test_note_post_auto_follows_the_author(self):
        account = Account.objects.create(name="Stream Co")
        Preferences.objects.create(
            user=self.user, auto_follow_entity_types=["Account"]
        )
        self.assertFalse(subscriptions.is_following(self.user, account))

        stream.post_note(account, "Hello", user=self.user)
        self.assertTrue(subscriptions.is_following(self.user, account))

    def test_note_post_does_not_follow_unlisted_types(self):
        Preferences.objects.create(
            user=self.user, auto_follow_entity_types=["Opportunity"]
        )
        account = Account.objects.create(name="Stream Plain Co")

        stream.post_note(account, "Hello", user=self.user)
        self.assertFalse(subscriptions.is_following(self.user, account))

    def test_fan_out_does_not_create_duplicates(self):
        Preferences.objects.create(
            user=self.user, auto_follow_entity_types=["Account"]
        )
        account = Account.objects.create(name="Once Co")
        subscriptions.auto_follow_created(account)

        self.assertEqual(
            StreamSubscription.objects.filter(
                user=self.user, entity_type="Account", entity_id=account.pk
            ).count(),
            1,
        )

    def test_inactive_preferences_are_ignored(self):
        Preferences.objects.create(
            user=self.user,
            auto_follow_entity_types=["Account"],
        )
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        account = Account.objects.create(name="Inactive Co")
        self.assertFalse(subscriptions.is_following(self.user, account))


class FollowerNotificationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("note-author", "na@example.com", "pw")
        self.follower = User.objects.create_user("note-follower", "nf@example.com", "pw")
        self.account = Account.objects.create(name="Notify Co")
        subscriptions.set_following(self.follower, self.account, True)

    def _stream_notifications(self, user):
        return Notification.objects.filter(
            user=user, type=Notification.Type.STREAM
        )

    def test_post_note_notifies_followers(self):
        stream.post_note(self.account, "Hello", user=self.author)
        self.assertEqual(self._stream_notifications(self.follower).count(), 1)

    def test_author_is_not_notified_about_own_post(self):
        stream.post_note(self.account, "Hello", user=self.follower)
        self.assertEqual(self._stream_notifications(self.follower).count(), 0)

    def test_inactive_followers_are_not_notified(self):
        self.follower.is_active = False
        self.follower.save(update_fields=["is_active"])

        stream.post_note(self.account, "Hello", user=self.author)
        self.assertEqual(self._stream_notifications(self.follower).count(), 0)

    def test_non_followers_are_not_notified(self):
        outsider = User.objects.create_user("note-outsider", "no@example.com", "pw")
        stream.post_note(self.account, "Hello", user=self.author)
        self.assertEqual(self._stream_notifications(outsider).count(), 0)

    def test_reactions_do_not_notify_followers(self):
        note = stream.post_note(self.account, "Hello", user=self.author)
        Notification.objects.all().delete()

        reactions.toggle_reaction(note, self.follower, "👍")
        self.assertEqual(Notification.objects.count(), 0)


class SubscriptionAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "subs-admin", "subs@example.com", "pw"
        )
        self.client.force_login(self.admin)

    def _toggle_url(self, kind, obj):
        return reverse(
            "admin:crm_task_subscription_toggle", args=[kind, obj.pk]
        )

    def test_star_toggle_endpoint_is_idempotent(self):
        task = Task.objects.create(name="Toggle task")
        response = self.client.post(self._toggle_url("star", task))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"value": True})
        self.assertTrue(subscriptions.is_starred(self.admin, task))

        response = self.client.post(self._toggle_url("star", task))
        self.assertJSONEqual(response.content, {"value": False})
        self.assertFalse(subscriptions.is_starred(self.admin, task))

    def test_follow_toggle_endpoint(self):
        task = Task.objects.create(name="Follow task")
        response = self.client.post(self._toggle_url("follow", task))
        self.assertJSONEqual(response.content, {"value": True})
        self.assertTrue(subscriptions.is_following(self.admin, task))

    def test_unknown_kind_is_rejected(self):
        task = Task.objects.create(name="Bad kind")
        response = self.client.post(self._toggle_url("bogus", task))
        self.assertEqual(response.status_code, 400)

    def test_changelist_renders_star_toggles(self):
        task = Task.objects.create(name="Visible task")
        subscriptions.set_starred(self.admin, task, True)

        response = self.client.get(reverse("admin:crm_task_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-subscription-toggle")
        self.assertContains(response, 'aria-pressed="true"')

    def test_change_form_renders_star_and_follow_controls(self):
        task = Task.objects.create(name="Detail task")
        response = self.client.get(
            reverse("admin:crm_task_change", args=[task.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-subscription-toggle")
        self.assertContains(response, 'data-icon-off="star_border"')
        self.assertContains(response, "Follow")

    def test_starred_list_filter(self):
        starred = Task.objects.create(name="Starred task")
        plain = Task.objects.create(name="Plain task")
        subscriptions.set_starred(self.admin, starred, True)

        response = self.client.get(
            reverse("admin:crm_task_changelist"), {"starred": "1"}
        )
        self.assertContains(response, "Starred task")
        self.assertNotContains(response, "Plain task")

        response = self.client.get(
            reverse("admin:crm_task_changelist"), {"starred": "0"}
        )
        self.assertContains(response, "Plain task")
        self.assertNotContains(response, "Starred task")

    def test_following_list_filter(self):
        followed = Task.objects.create(name="Followed task")
        plain = Task.objects.create(name="Unfollowed task")
        subscriptions.set_following(self.admin, followed, True)

        response = self.client.get(
            reverse("admin:crm_task_changelist"), {"following": "1"}
        )
        self.assertContains(response, "Followed task")
        self.assertNotContains(response, "Unfollowed task")

        response = self.client.get(
            reverse("admin:crm_task_changelist"), {"following": "0"}
        )
        self.assertContains(response, "Unfollowed task")
        self.assertNotContains(response, "Followed task")


class CustomEntitySubscriptionTests(TestCase):
    """Runtime custom entities share the same identity convention."""

    def setUp(self):
        self.user = User.objects.create_user("dyn-user", "dyn@example.com", "pw")
        self.entity = CustomEntity.objects.create(
            name="Widget", label="Widget", label_plural="Widgets"
        )
        registry.invalidate()
        self.addCleanup(self._cleanup)
        self.record = DynamicRecord.objects.create(
            entity_type="Widget", name="Apollo"
        )

    def _cleanup(self):
        DynamicRecord.objects.filter(entity_type="Widget").delete()
        custom_entities.unregister(self.entity)
        if self.entity.pk:
            self.entity.delete()
        registry.invalidate()

    def test_star_and_follow_a_custom_entity_record(self):
        self.assertTrue(subscriptions.set_starred(self.user, self.record, True))
        self.assertTrue(subscriptions.set_following(self.user, self.record, True))

        self.assertTrue(subscriptions.is_starred(self.user, self.record))
        self.assertTrue(subscriptions.is_following(self.user, self.record))
        self.assertEqual(list(subscriptions.followers_of(self.record)), [self.user])

    def test_annotation_uses_the_custom_entity_type(self):
        subscriptions.set_starred(self.user, self.record, True)

        rows = list(
            subscriptions.annotate_starred(
                DynamicRecord.objects.filter(entity_type="Widget"),
                self.user,
                "Widget",
            )
        )
        self.assertEqual([row.starred for row in rows], [True])


class PreferencesAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "pref-admin", "pref@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.user = User.objects.create_user("pref-user", "pu@example.com", "pw")

    def test_auto_follow_preference_is_saved(self):
        preferences = Preferences.objects.create(user=self.user)
        response = self.client.post(
            reverse("admin:core_preferences_change", args=[preferences.pk]),
            {
                "user": self.user.pk,
                "time_zone": "",
                "date_format": "",
                "time_format": "",
                "language": "en",
                "theme": "",
                "default_currency": "",
                "dashboard_layout": "{}",
                "preset_filters": "{}",
                "notifications_config": "{}",
                "auto_follow_entity_types": ["Account", "Task"],
            },
        )
        self.assertEqual(response.status_code, 302)
        preferences.refresh_from_db()
        self.assertEqual(
            set(preferences.auto_follow_entity_types), {"Account", "Task"}
        )

    def test_form_only_offers_stream_enabled_entities(self):
        from omacrm.core.admin.users import PreferencesAdminForm

        form = PreferencesAdminForm()
        values = {value for value, _label in form.fields["auto_follow_entity_types"].choices}
        self.assertIn("Account", values)
        self.assertNotIn("Preferences", values)

    def test_change_form_renders_auto_follow_field(self):
        preferences = Preferences.objects.create(user=self.user)
        response = self.client.get(
            reverse("admin:core_preferences_change", args=[preferences.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "auto_follow_entity_types")


class NoSubscriptionBehaviourTests(TestCase):
    def test_plain_records_behave_exactly_as_before(self):
        user = User.objects.create_user("plain-user", "plain@example.com", "pw")
        account = Account.objects.create(name="Plain Co")

        self.assertFalse(subscriptions.is_starred(user, account))
        self.assertFalse(subscriptions.is_following(user, account))
        self.assertEqual(subscriptions.followers_of(account).count(), 0)

        stream.post_note(account, "Nobody follows this", user=user)
        self.assertEqual(Notification.objects.count(), 0)

    def test_mentions_still_notify(self):
        author = User.objects.create_user("mention-author", "ma@example.com", "pw")
        mentioned = User.objects.create_user("mention-target", "mt@example.com", "pw")
        account = Account.objects.create(name="Mention Co")

        stream.post_note(account, "@mention-target please look", user=author)

        self.assertTrue(
            Notification.objects.filter(
                user=mentioned, type=Notification.Type.MENTION
            ).exists()
        )

from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import (
    Note,
    StarSubscription,
    StreamSubscription,
    User,
)
from omacrm.core.services import subscriptions
from omacrm.core.services.merge import merge_records
from omacrm.crm.models import Account, Contact


class MergeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("merge-admin", "merge@example.com", "pw")
        self.client.force_login(self.admin)
        self.left = Account.objects.create(name="Keep Co", phone_number="111")
        self.right = Account.objects.create(name="Dupe Co", phone_number="222")
        self.contact = Contact.objects.create(
            first_name="Con", last_name="Tact", account=self.right
        )
        self.note = Note.objects.create(
            type=Note.Type.POST, post="hello", parent=self.right
        )

    def _select(self, pk_list):
        return self.client.post(
            reverse("admin:crm_account_changelist"),
            {
                "action": "merge_selected",
                "_selected_action": pk_list,
                "index": "0",
                "select_across": "0",
            },
        )

    def test_action_requires_exactly_two_records(self):
        response = self._select([self.left.pk])
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("/merge/", response["Location"])

    def test_merge_page_and_post(self):
        location = self._select([self.left.pk, self.right.pk])["Location"]
        self.assertIn("/merge/", location)

        response = self.client.get(location)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep Co")
        self.assertContains(response, "Dupe Co")

        token = location.split("token=", 1)[1]
        response = self.client.post(
            reverse("admin:crm_account_merge"),
            {
                "token": token,
                "master": "left",
                "field__name": "right",
                "field__phone_number": "left",
            },
        )
        self.assertEqual(response.status_code, 302)

        master = Account.objects.get(pk=self.left.pk)
        self.assertEqual(master.name, "Dupe Co")
        self.assertEqual(master.phone_number, "111")

        self.assertFalse(Account.objects.filter(pk=self.right.pk).exists())
        self.assertTrue(Account.all_objects.filter(pk=self.right.pk).exists())

        self.contact.refresh_from_db()
        self.assertEqual(self.contact.account, master)

        self.note.refresh_from_db()
        self.assertEqual(self.note.parent, master)
        self.assertGreaterEqual(
            Note.objects.filter(
                parent_type__model="account", parent_id=master.pk
            ).count(),
            2,
        )

    def test_merge_can_keep_right_as_master(self):
        location = self._select([self.left.pk, self.right.pk])["Location"]
        token = location.split("token=", 1)[1]
        self.client.post(
            reverse("admin:crm_account_merge"),
            {"token": token, "master": "right"},
        )
        self.assertFalse(Account.objects.filter(pk=self.left.pk).exists())
        self.assertTrue(Account.objects.filter(pk=self.right.pk).exists())
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.account_id, self.right.pk)

    def test_subscriptions_move_to_the_master(self):
        fan = User.objects.create_user("merge-fan", "fan@example.com", "pw")
        subscriptions.set_starred(fan, self.right, True)
        subscriptions.set_following(fan, self.right, True)

        moved = merge_records(self.left, self.right)

        self.assertEqual(moved["stars"], 1)
        self.assertEqual(moved["follows"], 1)
        self.assertTrue(subscriptions.is_starred(fan, self.left))
        self.assertTrue(subscriptions.is_following(fan, self.left))
        self.assertFalse(
            StarSubscription.objects.filter(
                entity_type="Account", entity_id=self.right.pk
            ).exists()
        )
        self.assertFalse(
            StreamSubscription.objects.filter(
                entity_type="Account", entity_id=self.right.pk
            ).exists()
        )

    def test_subscriber_of_both_keeps_one_row_on_the_master(self):
        fan = User.objects.create_user("merge-both", "both@example.com", "pw")
        subscriptions.set_starred(fan, self.left, True)
        subscriptions.set_starred(fan, self.right, True)
        subscriptions.set_following(fan, self.left, True)
        subscriptions.set_following(fan, self.right, True)

        moved = merge_records(self.left, self.right)

        self.assertEqual(moved["stars"], 1)
        self.assertEqual(moved["follows"], 1)
        self.assertEqual(
            StarSubscription.objects.filter(
                user=fan, entity_type="Account", entity_id=self.left.pk
            ).count(),
            1,
        )
        self.assertEqual(
            StreamSubscription.objects.filter(
                user=fan, entity_type="Account", entity_id=self.left.pk
            ).count(),
            1,
        )
        self.assertFalse(
            StarSubscription.objects.filter(
                entity_type="Account", entity_id=self.right.pk
            ).exists()
        )
        self.assertFalse(
            StreamSubscription.objects.filter(
                entity_type="Account", entity_id=self.right.pk
            ).exists()
        )

    def test_merge_without_subscriptions_is_unchanged(self):
        moved = merge_records(self.left, self.right)

        self.assertEqual(moved["stars"], 0)
        self.assertEqual(moved["follows"], 0)
        self.assertTrue(Account.objects.filter(pk=self.left.pk).exists())
        self.assertFalse(Account.objects.filter(pk=self.right.pk).exists())

    def test_invalid_token(self):
        response = self.client.get(
            reverse("admin:crm_account_merge"), {"token": "nope"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid")

        response = self.client.post(
            reverse("admin:crm_account_merge"),
            {"token": "nope"},
            follow=True,
        )
        self.assertContains(response, "selection expired")

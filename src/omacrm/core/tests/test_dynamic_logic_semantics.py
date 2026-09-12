"""Semantics of dynamic logic that the feature must never regress.

These lock the behaviour that is easy to get subtly wrong: rules read the
SUBMITTED values rather than the stored instance, rules are scoped per entity,
a new rule applies without a process restart, and falsy-but-present values
(False, 0) are not empty.
"""

from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import DynamicLogic
from omacrm.core.services import dynamic_logic
from omacrm.crm.models import Account

try:  # the prefix the existing admin tests use for the attachment inline
    from omacrm.core.tests.test_dynamic_logic import ATTACHMENT_PREFIX
except ImportError:  # pragma: no cover
    ATTACHMENT_PREFIX = "attachments"


class DynamicLogicIndependentTests(TestCase):
    def setUp(self):
        from omacrm.core.models import User

        self.admin = User.objects.create_superuser(
            "verif-admin", "verif@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.addCleanup(dynamic_logic.invalidate_dynamic_logic_cache)

    def _data(self, **extra):
        data = {
            "name": "Acme",
            "assigned_user": "",
            "teams": [],
            "_save": "Save",
            f"{ATTACHMENT_PREFIX}-TOTAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-INITIAL_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MIN_NUM_FORMS": "0",
            f"{ATTACHMENT_PREFIX}-MAX_NUM_FORMS": "1000",
            "contact_links-TOTAL_FORMS": "0",
            "contact_links-INITIAL_FORMS": "0",
            "contact_links-MIN_NUM_FORMS": "0",
            "contact_links-MAX_NUM_FORMS": "1000",
        }
        data.update(extra)
        return data

    def _rule(self, action, condition, field_name="description", entity="Account"):
        return DynamicLogic.objects.create(
            entity_type=entity,
            field_name=field_name,
            action=action,
            condition=condition,
        )

    def _required_unless_closed(self):
        """`description` is required unless the submitted name is Closed Co."""
        return self._rule(
            DynamicLogic.Action.REQUIRED,
            {
                "type": "not",
                "value": {
                    "type": "equals",
                    "attribute": "name",
                    "value": "Closed Co",
                },
            },
        )

    # -- the crux: submitted values win over the stored instance -------------

    def test_save_is_allowed_when_only_the_stored_value_matches(self):
        # Stored name matches the condition; the submitted one does not. If the
        # rules were evaluated against the stored instance the save would be
        # blocked. It must go through.
        account = Account.objects.create(name="Acme")
        self._required_unless_closed()
        response = self.client.post(
            reverse("admin:crm_account_change", args=[account.pk]),
            self._data(name="Closed Co"),
        )
        self.assertEqual(response.status_code, 302, response.content)

    def test_save_is_blocked_when_the_submitted_value_matches(self):
        # Stored name does NOT match; the submitted one does. Must be blocked.
        account = Account.objects.create(name="Closed Co")
        self._required_unless_closed()
        response = self.client.post(
            reverse("admin:crm_account_change", args=[account.pk]),
            self._data(name="Acme"),
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertIn("description", form.errors)

    # -- scoping and cache freshness ---------------------------------------

    def test_rules_are_scoped_to_their_entity(self):
        self._rule(
            DynamicLogic.Action.REQUIRED,
            {"type": "isNotEmpty", "attribute": "name"},
        )
        self.assertEqual(len(dynamic_logic.active_rules("Account")), 1)
        self.assertEqual(dynamic_logic.active_rules("Contact"), [])

    def test_new_rule_applies_without_a_restart(self):
        # Warm the cache while there are no rules, then create one.
        self.assertEqual(dynamic_logic.active_rules("Account"), [])
        self.assertFalse(
            dynamic_logic.field_states("Account", {"name": "Acme"})["description"][
                "required"
            ]
        )
        self._required_unless_closed()
        self.assertTrue(
            dynamic_logic.field_states("Account", {"name": "Acme"})["description"][
                "required"
            ]
        )

    # -- readonly ----------------------------------------------------------

    def test_readonly_field_keeps_the_stored_value(self):
        account = Account.objects.create(name="Acme", description="original")
        self._rule(
            DynamicLogic.Action.READONLY,
            {"type": "isNotEmpty", "attribute": "name"},
        )
        response = self.client.post(
            reverse("admin:crm_account_change", args=[account.pk]),
            self._data(name="Acme", description="tampered"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        account.refresh_from_db()
        self.assertEqual(account.description, "original")

    # -- semantic edges of empty vs falsy ----------------------------------

    def test_falsy_but_present_values_are_not_empty(self):
        for value in (False, 0, "0"):
            with self.subTest(value=value):
                self.assertFalse(
                    dynamic_logic.evaluate(
                        {"type": "isEmpty", "attribute": "x"}, {"x": value}
                    ),
                    f"{value!r} must not count as empty",
                )
                self.assertTrue(
                    dynamic_logic.evaluate(
                        {"type": "isNotEmpty", "attribute": "x"}, {"x": value}
                    )
                )
        for value in (None, "", [], {}):
            with self.subTest(value=value):
                self.assertTrue(
                    dynamic_logic.evaluate(
                        {"type": "isEmpty", "attribute": "x"}, {"x": value}
                    )
                )

    def test_numeric_strings_compare_numerically(self):
        self.assertTrue(
            dynamic_logic.evaluate(
                {"type": "greaterThanOrEquals", "attribute": "amount", "value": 1000},
                {"amount": "1500.50"},
            )
        )
        self.assertFalse(
            dynamic_logic.evaluate(
                {"type": "greaterThan", "attribute": "amount", "value": 1000},
                {"amount": "999"},
            )
        )
        # a missing attribute must not raise nor match
        self.assertFalse(
            dynamic_logic.evaluate(
                {"type": "greaterThan", "attribute": "amount", "value": 0}, {}
            )
        )

    def test_malformed_conditions_are_inert(self):
        for condition in (
            None,
            [],
            "nonsense",
            {"type": "noSuchOperator", "attribute": "x"},
            {"type": "equals"},
            {"type": "and", "value": "not-a-list"},
            {"type": "not", "value": [{"type": "isTrue", "attribute": "x"}]},
            {"type": "equals", "attribute": "x", "value": {"unhashable": [1, 2]}},
        ):
            with self.subTest(condition=condition):
                self.assertFalse(dynamic_logic.evaluate(condition, {"x": 1}))

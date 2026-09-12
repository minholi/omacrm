from datetime import date, datetime, time, timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from omacrm.core.models import DynamicLogic, User
from omacrm.core.services import dynamic_logic
from omacrm.core.services.dynamic_logic import (
    condition_errors,
    evaluate,
    field_states,
    frontend_config,
)
from omacrm.crm.models import Account

ATTACHMENT_PREFIX = "core-attachment-related_type-related_id"


class DynamicLogicOperatorTests(SimpleTestCase):
    def assert_match(self, condition, values, expected=True):
        self.assertEqual(
            evaluate(condition, values), expected, msg=f"{condition} vs {values}"
        )

    # -- equality -----------------------------------------------------------

    def test_equals_and_not_equals(self):
        self.assert_match(
            {"type": "equals", "attribute": "status", "value": "Open"},
            {"status": "Open"},
        )
        self.assert_match(
            {"type": "equals", "attribute": "status", "value": "Open"},
            {"status": "Closed"},
            False,
        )
        self.assert_match(
            {"type": "notEquals", "attribute": "status", "value": "Open"},
            {"status": "Closed"},
        )
        self.assert_match(
            {"type": "notEquals", "attribute": "status", "value": "Open"},
            {"status": "Open"},
            False,
        )
        # Unknown attributes resolve to None.
        self.assert_match(
            {"type": "equals", "attribute": "missing", "value": ""}, {}, False
        )

    def test_equals_is_type_aware(self):
        equality = {"type": "equals", "attribute": "amount", "value": 5}
        self.assert_match(equality, {"amount": 5})
        self.assert_match(equality, {"amount": "5"})
        self.assert_match(equality, {"amount": "5.0"})
        self.assert_match(equality, {"amount": "five"}, False)
        self.assert_match(
            {"type": "equals", "attribute": "flag", "value": True},
            {"flag": "true"},
        )
        self.assert_match(
            {"type": "equals", "attribute": "flag", "value": False},
            {"flag": "0"},
        )

    def test_is_true_and_is_false(self):
        is_true = {"type": "isTrue", "attribute": "flag"}
        is_false = {"type": "isFalse", "attribute": "flag"}
        for truthy in (True, 1, "1", "true", "yes", "on"):
            self.assert_match(is_true, {"flag": truthy})
        for falsy in (False, 0, "0", "false", "no", "off"):
            self.assert_match(is_false, {"flag": falsy})
        self.assert_match(is_true, {"flag": ""}, False)
        self.assert_match(is_false, {"flag": ""}, False)
        self.assert_match(is_true, {"flag": None}, False)

    def test_is_empty_and_is_not_empty(self):
        is_empty = {"type": "isEmpty", "attribute": "value"}
        is_not_empty = {"type": "isNotEmpty", "attribute": "value"}
        for empty in (None, "", [], {}):
            self.assert_match(is_empty, {"value": empty})
        for filled in ("x", 0, False, [1]):
            self.assert_match(is_empty, {"value": filled}, False)
        self.assert_match(is_not_empty, {"value": "x"})
        self.assert_match(is_not_empty, {"value": None}, False)

    # -- strings ------------------------------------------------------------

    def test_string_operators(self):
        self.assert_match(
            {"type": "contains", "attribute": "name", "value": "acme"},
            {"name": "Acme Corp"},
            False,
        )
        self.assert_match(
            {"type": "contains", "attribute": "name", "value": "Acme"},
            {"name": "Acme Corp"},
        )
        self.assert_match(
            {"type": "notContains", "attribute": "name", "value": "zzz"},
            {"name": "Acme Corp"},
        )
        self.assert_match(
            {"type": "startsWith", "attribute": "name", "value": "Ac"},
            {"name": "Acme Corp"},
        )
        self.assert_match(
            {"type": "endsWith", "attribute": "name", "value": "Corp"},
            {"name": "Acme Corp"},
        )
        self.assert_match(
            {"type": "matches", "attribute": "code", "value": r"^A-\d+$"},
            {"code": "A-42"},
        )
        self.assert_match(
            {"type": "matches", "attribute": "code", "value": "("},
            {"code": "A-42"},
            False,
        )
        self.assert_match(
            {"type": "contains", "attribute": "name", "value": "x"}, {"name": None}, False
        )
        self.assert_match(
            {"type": "notContains", "attribute": "name", "value": "x"},
            {"name": None},
        )

    # -- collections --------------------------------------------------------

    def test_collection_operators(self):
        self.assert_match(
            {"type": "has", "attribute": "tags", "value": "vip"},
            {"tags": ["vip", "lead"]},
        )
        self.assert_match(
            {"type": "has", "attribute": "tags", "value": 2},
            {"tags": ["1", 2]},
        )
        self.assert_match(
            {"type": "notHas", "attribute": "tags", "value": "vip"},
            {"tags": []},
        )
        self.assert_match(
            {"type": "in", "attribute": "status", "value": ["New", "Open"]},
            {"status": "Open"},
        )
        self.assert_match(
            {"type": "in", "attribute": "status", "value": ["New", "Open"]},
            {"status": "Closed"},
            False,
        )
        self.assert_match(
            {"type": "notIn", "attribute": "status", "value": ["New", "Open"]},
            {"status": "Closed"},
        )
        self.assert_match(
            {"type": "in", "attribute": "status", "value": ["1", "2"]},
            {"status": 1},
        )

    # -- numbers ------------------------------------------------------------

    def test_number_operators(self):
        self.assert_match(
            {"type": "greaterThan", "attribute": "amount", "value": 10},
            {"amount": "10.5"},
        )
        self.assert_match(
            {"type": "lessThan", "attribute": "amount", "value": 10},
            {"amount": "9.5"},
        )
        self.assert_match(
            {"type": "greaterThanOrEquals", "attribute": "amount", "value": "10"},
            {"amount": 10},
        )
        self.assert_match(
            {"type": "lessThanOrEquals", "attribute": "amount", "value": "10"},
            {"amount": 10},
        )
        self.assert_match(
            {"type": "greaterThan", "attribute": "amount", "value": 10},
            {"amount": "n/a"},
            False,
        )
        self.assert_match(
            {"type": "greaterThan", "attribute": "amount", "value": 10},
            {"amount": None},
            False,
        )
        self.assert_match(
            {"type": "greaterThan", "attribute": "amount", "value": 0},
            {"amount": True},
            False,
        )

    # -- dates --------------------------------------------------------------

    def test_date_operators(self):
        today = timezone.localdate()
        self.assert_match({"type": "isToday", "attribute": "d"}, {"d": today})
        self.assert_match(
            {"type": "isToday", "attribute": "d"}, {"d": today.isoformat()}
        )
        self.assert_match({"type": "isToday", "attribute": "d"}, {"d": timezone.now()})
        self.assert_match(
            {"type": "isToday", "attribute": "d"},
            {"d": datetime.combine(today, time(9, 30))},
        )
        self.assert_match(
            {"type": "isToday", "attribute": "d"},
            {"d": datetime.combine(today - timedelta(days=1), time(9, 30))},
            False,
        )
        self.assert_match(
            {"type": "inFuture", "attribute": "d"},
            {"d": timezone.now() + timedelta(days=1)},
        )
        self.assert_match(
            {"type": "inPast", "attribute": "d"},
            {"d": timezone.now() - timedelta(days=1)},
        )
        self.assert_match(
            {"type": "inFuture", "attribute": "d"},
            {"d": "not-a-date"},
            False,
        )
        self.assert_match({"type": "isToday", "attribute": "d"}, {"d": None}, False)

    def test_datetime_equality_naive_vs_aware(self):
        aware = timezone.make_aware(datetime(2026, 1, 2, 10, 0))
        self.assert_match(
            {"type": "equals", "attribute": "d", "value": "2026-01-02T10:00:00"},
            {"d": aware},
        )
        self.assert_match(
            {"type": "equals", "attribute": "d", "value": date(2026, 1, 2)},
            {"d": date(2026, 1, 2)},
        )

    # -- groups -------------------------------------------------------------

    def test_nested_groups(self):
        condition = {
            "type": "and",
            "value": [
                {"type": "equals", "attribute": "status", "value": "Open"},
                {
                    "type": "or",
                    "value": [
                        {"type": "greaterThan", "attribute": "amount", "value": 100},
                        {
                            "type": "not",
                            "value": {
                                "type": "isEmpty",
                                "attribute": "email_address",
                            },
                        },
                    ],
                },
            ],
        }
        self.assertTrue(
            evaluate(condition, {"status": "Open", "amount": 150})
        )
        self.assertTrue(
            evaluate(
                condition,
                {"status": "Open", "amount": 50, "email_address": "a@b.c"},
            )
        )
        self.assertFalse(
            evaluate(condition, {"status": "Open", "amount": 50, "email_address": ""})
        )
        self.assertFalse(
            evaluate(condition, {"status": "Closed", "amount": 150})
        )

    # -- malformed ----------------------------------------------------------

    def test_malformed_conditions_never_raise(self):
        malformed = [
            None,
            "equals",
            [],
            {},
            {"type": "unknown", "attribute": "x"},
            {"type": "equals"},
            {"type": "and", "value": "not-a-list"},
            {"type": "and", "value": [None, {"type": "equals"}]},
            {"type": "or", "value": [{"type": "and", "value": 1}]},
            {"type": "not", "value": "not-a-node"},
            {"type": "matches", "attribute": "x", "value": None},
            {"type": "in", "attribute": "x", "value": 5},
        ]
        for condition in malformed:
            self.assertIs(evaluate(condition, {"x": "1"}), False, msg=str(condition))

    def test_condition_errors(self):
        self.assertEqual(condition_errors({"type": "equals", "attribute": "x", "value": 1}), [])
        self.assertTrue(condition_errors({"type": "bogus"}))
        self.assertTrue(condition_errors({"type": "not", "value": []}))
        self.assertTrue(condition_errors({"type": "and", "value": []}))
        self.assertTrue(condition_errors({"type": "equals", "value": 1}))
        self.assertTrue(
            condition_errors(
                {"type": "or", "value": [{"type": "equals", "attribute": "x"}]}
            )
        )


class DynamicLogicFieldStateTests(TestCase):
    def setUp(self):
        self.addCleanup(dynamic_logic.invalidate_dynamic_logic_cache)

    def test_defaults_without_rules(self):
        states = field_states("Account", {})
        self.assertEqual(
            states["name"], {"visible": True, "required": True, "readonly": False}
        )
        self.assertEqual(
            states["description"],
            {"visible": True, "required": False, "readonly": False},
        )
        self.assertEqual(field_states("Account", {}), frontend_config("Account")["fields"])

    def test_visible_rule(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "equals", "attribute": "industry", "value": "Tech"},
        )
        states = field_states("Account", {"industry": "Tech"})
        self.assertTrue(states["description"]["visible"])
        states = field_states("Account", {"industry": "Retail"})
        self.assertFalse(states["description"]["visible"])

    def test_required_rule(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.REQUIRED,
            condition={"type": "equals", "attribute": "name", "value": "Need"},
        )
        states = field_states("Account", {"name": "Need"})
        self.assertTrue(states["description"]["required"])
        states = field_states("Account", {"name": "Other"})
        self.assertFalse(states["description"]["required"])

    def test_required_rule_overrides_metadata_required(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="name",
            action=DynamicLogic.Action.REQUIRED,
            condition={"type": "equals", "attribute": "industry", "value": "Tech"},
        )
        self.assertTrue(
            field_states("Account", {"industry": "Tech"})["name"]["required"]
        )
        self.assertFalse(
            field_states("Account", {"industry": "Retail"})["name"]["required"]
        )

    def test_readonly_rule(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.READONLY,
            condition={"type": "isTrue", "attribute": "is_locked"},
        )
        self.assertTrue(field_states("Account", {"is_locked": True})["description"]["readonly"])
        self.assertFalse(field_states("Account", {"is_locked": False})["description"]["readonly"])

    def test_multiple_rules_for_an_action_are_ored(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "equals", "attribute": "industry", "value": "Tech"},
        )
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "equals", "attribute": "industry", "value": "Retail"},
        )
        self.assertTrue(
            field_states("Account", {"industry": "Retail"})["description"]["visible"]
        )
        self.assertFalse(
            field_states("Account", {"industry": "Finance"})["description"]["visible"]
        )

    def test_inactive_and_foreign_rules_are_ignored(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "isTrue", "attribute": "is_locked"},
            is_active=False,
        )
        DynamicLogic.objects.create(
            entity_type="Contact",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "isTrue", "attribute": "do_not_call"},
        )
        self.assertTrue(field_states("Account", {"is_locked": True})["description"]["visible"])

    def test_frontend_config_shape(self):
        DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.REQUIRED,
            condition={"type": "equals", "attribute": "name", "value": "Need"},
        )
        config = frontend_config("Account")
        self.assertEqual(config["entityType"], "Account")
        self.assertTrue(config["fields"]["name"]["required"])
        self.assertEqual(len(config["rules"]), 1)
        rule = config["rules"][0]
        self.assertEqual(rule["field"], "description")
        self.assertEqual(rule["action"], "required")
        self.assertEqual(rule["condition"]["attribute"], "name")

    def test_cache_invalidates_on_save_and_delete(self):
        rule = DynamicLogic.objects.create(
            entity_type="Account",
            field_name="description",
            action=DynamicLogic.Action.VISIBLE,
            condition={"type": "isTrue", "attribute": "is_locked"},
        )
        values = {"is_locked": False}
        self.assertFalse(field_states("Account", values)["description"]["visible"])
        rule.is_active = False
        rule.save()
        self.assertTrue(field_states("Account", values)["description"]["visible"])
        rule.is_active = True
        rule.save()
        rule.delete()
        self.assertTrue(field_states("Account", values)["description"]["visible"])


class DynamicLogicRuleAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "rule-admin", "rule@example.com", "pw"
        )
        self.client.force_login(self.admin)
        self.addCleanup(dynamic_logic.invalidate_dynamic_logic_cache)

    def _data(self, **extra):
        data = {
            "entity_type": "Account",
            "field_name": "description",
            "action": "required",
            "condition": '{"type": "equals", "attribute": "name", "value": "X"}',
            "is_active": "on",
            "_save": "Save",
        }
        data.update(extra)
        return data

    def test_rule_created_through_the_admin(self):
        response = self.client.post(
            reverse("admin:core_dynamiclogic_add"), self._data()
        )
        self.assertEqual(response.status_code, 302, response.content)
        rule = DynamicLogic.objects.get()
        self.assertEqual(rule.condition["attribute"], "name")

    def test_admin_rejects_unknown_operator(self):
        response = self.client.post(
            reverse("admin:core_dynamiclogic_add"),
            self._data(condition='{"type": "bogus"}'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "unknown operator")
        self.assertFalse(DynamicLogic.objects.exists())

    def test_admin_rejects_unknown_field(self):
        response = self.client.post(
            reverse("admin:core_dynamiclogic_add"),
            self._data(field_name="not_a_field"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unknown field for this entity.")
        self.assertFalse(DynamicLogic.objects.exists())


class DynamicLogicAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "logic-admin", "logic@example.com", "pw"
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

    def _rule(self, action, condition, field_name="description"):
        return DynamicLogic.objects.create(
            entity_type="Account",
            field_name=field_name,
            action=action,
            condition=condition,
        )

    def test_normal_save_without_rules_is_unaffected(self):
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="Plain Co", description="plain"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        account = Account.objects.get(name="Plain Co")
        self.assertEqual(account.description, "plain")

    def test_hidden_field_submitted_value_is_ignored(self):
        account = Account.objects.create(name="Keep Co", description="keep")
        self._rule(
            DynamicLogic.Action.VISIBLE,
            {"type": "equals", "attribute": "name", "value": "Visible Co"},
        )
        response = self.client.post(
            reverse("admin:crm_account_change", args=[account.pk]),
            self._data(name="Keep Co", description="replaced"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        account.refresh_from_db()
        self.assertEqual(account.description, "keep")

    def test_hidden_required_field_does_not_block_save(self):
        self._rule(
            DynamicLogic.Action.VISIBLE,
            {"type": "equals", "attribute": "description", "value": "show"},
            field_name="name",
        )
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="", description="hide"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(Account.objects.filter(name="").exists())

    def test_conditionally_required_field_blocks_when_condition_holds(self):
        self._rule(
            DynamicLogic.Action.REQUIRED,
            {"type": "equals", "attribute": "name", "value": "Needs Description"},
        )
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="Needs Description", description=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(Account.objects.filter(name="Needs Description").exists())

    def test_conditionally_required_field_saves_when_condition_does_not_hold(self):
        self._rule(
            DynamicLogic.Action.REQUIRED,
            {"type": "equals", "attribute": "name", "value": "Needs Description"},
        )
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="Other Co", description=""),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(Account.objects.filter(name="Other Co").exists())

    def test_required_rule_does_not_block_a_metadata_required_field(self):
        # ``name`` is required in metadata; the rule only matters while the
        # condition holds, so an empty name saves when the condition is false.
        self._rule(
            DynamicLogic.Action.REQUIRED,
            {"type": "equals", "attribute": "industry", "value": "Tech"},
            field_name="name",
        )
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="", industry=""),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(Account.objects.filter(name="").exists())

    def test_readonly_rule_ignores_submitted_value(self):
        account = Account.objects.create(name="Locked Co", description="original")
        self._rule(
            DynamicLogic.Action.READONLY,
            {"type": "equals", "attribute": "name", "value": "Locked Co"},
        )
        response = self.client.post(
            reverse("admin:crm_account_change", args=[account.pk]),
            self._data(name="Locked Co", description="hacked"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        account.refresh_from_db()
        self.assertEqual(account.description, "original")

    def test_change_form_exposes_json_config(self):
        self._rule(
            DynamicLogic.Action.REQUIRED,
            {"type": "equals", "attribute": "name", "value": "Needs Description"},
        )
        response = self.client.get(
            reverse("admin:crm_account_change", args=[Account.objects.create(name="A").pk])
        )
        self.assertContains(response, 'id="dynamic-logic-config"')
        self.assertContains(response, '"entityType": "Account"')
        self.assertContains(response, '"field": "description"')

    def test_malformed_rule_does_not_break_the_form(self):
        self._rule(DynamicLogic.Action.VISIBLE, {"type": "bogus"})
        response = self.client.post(
            reverse("admin:crm_account_add"),
            self._data(name="Malformed Co", description="fine"),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(Account.objects.filter(name="Malformed Co").exists())

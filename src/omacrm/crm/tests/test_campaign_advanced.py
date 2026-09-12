from decimal import Decimal

from djmoney.money import Money
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import User
from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    Contact,
    EmailQueueItem,
    EmailTemplate,
    Lead,
    LeadCapture,
    MassEmail,
    Opportunity,
    TargetList,
    TargetListMember,
)
from omacrm.crm.services.campaigns import recalc_revenue, record_bounce
from omacrm.crm.services.mass_email import (
    build_queue,
    process_mass_email,
    unsubscribe_token,
    unsubscribe_url,
)


class CampaignRevenueTests(TestCase):
    def test_revenue_follows_closed_won_opportunities(self):
        campaign = Campaign.objects.create(name="Q1")
        opportunity = Opportunity.objects.create(
            name="Deal",
            campaign=campaign,
            amount=Money(1000, "USD"),
            stage="Proposal",
        )
        campaign.refresh_from_db()
        self.assertEqual(campaign.revenue, Decimal("0.00"))

        opportunity.stage = "Closed Won"
        opportunity.save()
        campaign.refresh_from_db()
        self.assertEqual(campaign.revenue, Decimal("1000.00"))

        opportunity.amount = Money(500, "USD")
        opportunity.save()
        campaign.refresh_from_db()
        self.assertEqual(campaign.revenue, Decimal("500.00"))

    def test_recalc_revenue_direct(self):
        campaign = Campaign.objects.create(name="Direct")
        Opportunity.objects.create(
            name="Won", campaign=campaign, amount=Money(250, "USD"), stage="Closed Won"
        )
        self.assertEqual(recalc_revenue(campaign), Decimal("250.00"))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MassEmailUnsubscribeTests(TestCase):
    def setUp(self):
        self.target_list = TargetList.objects.create(name="Newsletter")
        self.contact = Contact.objects.create(
            first_name="Opt", last_name="Out", email_address="opt@example.com"
        )
        from omacrm.crm.services.target_lists import add_to_target_list

        add_to_target_list(self.contact, self.target_list)

        self.template = EmailTemplate.objects.create(
            name="Blast",
            subject="Hi",
            source="<p>Hello</p>",
            source_format="html",
        )
        self.campaign = Campaign.objects.create(name="Blast campaign")
        self.mass_email = MassEmail.objects.create(
            name="Blast", email_template=self.template, campaign=self.campaign
        )
        self.mass_email.target_lists.add(self.target_list)

    def test_sent_email_contains_unsubscribe_link(self):
        build_queue(self.mass_email)
        process_mass_email(
            type("Job", (), {"data": {"mass_email_id": self.mass_email.pk}})()
        )
        item = self.mass_email.queue_items.first()
        self.assertIn(unsubscribe_url(item), mail.outbox[0].body)

    def test_unsubscribe_opts_out_and_logs(self):
        build_queue(self.mass_email)
        item = self.mass_email.queue_items.first()

        response = self.client.get(
            reverse("mass_email_unsubscribe", args=[unsubscribe_token(item)])
        )
        self.assertEqual(response.status_code, 200)

        member = TargetListMember.objects.get(
            target_list=self.target_list, entity_id=self.contact.pk
        )
        self.assertTrue(member.opted_out)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.opted_out_count, 1)
        self.assertTrue(
            CampaignLogRecord.objects.filter(
                campaign=self.campaign,
                action=CampaignLogRecord.Action.OPTED_OUT,
            ).exists()
        )

    def test_invalid_unsubscribe_token(self):
        response = self.client.get(
            reverse("mass_email_unsubscribe", args=["invalid-token"])
        )
        self.assertEqual(response.status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BounceTests(TestCase):
    def setUp(self):
        self.target_list = TargetList.objects.create(name="Bounce list")
        self.contact = Contact.objects.create(
            first_name="Bounce", last_name="Target", email_address="bounce@example.com"
        )
        from omacrm.crm.services.target_lists import add_to_target_list

        add_to_target_list(self.contact, self.target_list)

        self.template = EmailTemplate.objects.create(
            name="T", subject="s", source="b", source_format="html"
        )
        self.campaign = Campaign.objects.create(name="Bounce campaign")
        self.mass_email = MassEmail.objects.create(
            name="Bounce blast", email_template=self.template, campaign=self.campaign
        )
        self.mass_email.target_lists.add(self.target_list)
        build_queue(self.mass_email)
        self.item = self.mass_email.queue_items.first()

    def test_record_bounce_marks_item_and_campaign(self):
        record = record_bounce(self.item, "Hard")
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, EmailQueueItem.Status.FAILED)
        self.assertEqual(record.bounced_type, "Hard")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.bounced_count, 1)

    def test_invalid_bounce_type(self):
        with self.assertRaises(ValueError):
            record_bounce(self.item, "Weird")

    def test_admin_bounce_action(self):
        admin = User.objects.create_superuser("bounce-admin", "ba@example.com", "pw")
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin:crm_emailqueueitem_changelist"),
            {
                "action": "mark_bounced_soft",
                "_selected_action": [self.item.pk],
                "index": "0",
                "select_across": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.last_error, "Soft bounce")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.bounced_count, 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LeadCaptureOptInTests(TestCase):
    def setUp(self):
        self.target_list = TargetList.objects.create(name="Opt-in leads")
        self.template = EmailTemplate.objects.create(
            name="Confirm",
            subject="Confirm your subscription",
            source="<p>Please confirm</p>",
            source_format="html",
        )
        self.capture = LeadCapture.objects.create(
            name="Opt-in form",
            target_list=self.target_list,
            source="Web Site",
            opt_in_confirmation=True,
            opt_in_template=self.template,
        )

    def _capture(self):
        return self.client.post(
            reverse("lead_capture", args=[self.capture.api_key]),
            data='{"first_name": "Opt", "last_name": "In", "email_address": "optin@example.com"}',
            content_type="application/json",
        )

    def test_capture_defers_target_list_until_confirmation(self):
        response = self._capture()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending_confirmation")

        lead = Lead.objects.get(last_name="In")
        self.assertFalse(lead.opt_in_confirmed)
        self.assertFalse(
            TargetListMember.objects.filter(
                target_list=self.target_list, entity_id=lead.pk
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/lead-capture/confirm/", mail.outbox[0].body)

        import re

        url = re.search(r"https?://[^\s]+/lead-capture/confirm/[^\s<]+", mail.outbox[0].body)
        self.assertIsNotNone(url)
        response = self.client.get(url.group(0))
        self.assertEqual(response.status_code, 200)

        lead.refresh_from_db()
        self.assertTrue(lead.opt_in_confirmed)
        self.assertIsNotNone(lead.opt_in_confirmed_at)
        self.assertTrue(
            TargetListMember.objects.filter(
                target_list=self.target_list, entity_id=lead.pk
            ).exists()
        )

    def test_invalid_confirmation_token(self):
        response = self.client.get(
            reverse("lead_capture_confirm", args=["invalid"])
        )
        self.assertEqual(response.status_code, 400)

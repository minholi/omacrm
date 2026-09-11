import json
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from omacrm.core.models import Note, User
from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    CampaignTrackingUrl,
    Contact,
    EmailQueueItem,
    EmailTemplate,
    Lead,
    LeadCapture,
    MassEmail,
    TargetList,
    TargetListMember,
)
from omacrm.crm.services.mass_email import build_queue, process_mass_email
from omacrm.crm.services.target_lists import (
    add_to_target_list,
    remove_from_target_list,
)


class TargetListTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("tl-admin", "tl@example.com", "pw")
        self.target_list = TargetList.objects.create(name="Newsletter")
        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", email_address="jane@example.com"
        )

    def test_add_opt_out_and_remove(self):
        add_to_target_list(self.contact, self.target_list)
        self.assertEqual(self.target_list.entry_count, 1)
        self.assertEqual(self.target_list.opted_out_count, 0)

        add_to_target_list(self.contact, self.target_list, opted_out=True)
        member = TargetListMember.objects.get()
        self.assertTrue(member.opted_out)
        self.assertEqual(self.target_list.opted_out_count, 1)

        remove_from_target_list(self.contact, self.target_list)
        self.assertEqual(self.target_list.entry_count, 0)

    def test_admin_action(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/admin/crm/contact/{self.contact.pk}/add_to_target_list_action/",
            {
                "_form_submitted": "on",
                "target_list": self.target_list.pk,
                "opted_out": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TargetListMember.objects.filter(target_list=self.target_list).exists())


class CampaignTrackingTests(TestCase):
    def setUp(self):
        self.campaign = Campaign.objects.create(name="Launch", status="Active")
        self.tracking = CampaignTrackingUrl.objects.create(
            campaign=self.campaign, name="Landing", url="https://example.com/landing"
        )

    def test_click_redirects_and_logs(self):
        response = self.client.get(reverse("campaign_track_click", args=[self.tracking.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/landing")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.clicked_count, 1)
        self.assertTrue(
            CampaignLogRecord.objects.filter(
                campaign=self.campaign, action=CampaignLogRecord.Action.CLICKED
            ).exists()
        )

    def test_show_message_action(self):
        self.tracking.action = CampaignTrackingUrl.Action.SHOW_MESSAGE
        self.tracking.message = "Thanks for your interest"
        self.tracking.save()
        response = self.client.get(reverse("campaign_track_click", args=[self.tracking.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thanks for your interest")

    def test_open_pixel(self):
        response = self.client.get(reverse("campaign_track_open", args=[self.campaign.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/gif")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.opened_count, 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MassEmailTests(TestCase):
    def setUp(self):
        self.target_list = TargetList.objects.create(name="Prospects")
        self.good = Contact.objects.create(
            first_name="Good", last_name="Recipient", email_address="good@example.com"
        )
        self.opted_out = Contact.objects.create(
            first_name="Opted", last_name="Out", email_address="out@example.com"
        )
        self.no_email = Contact.objects.create(first_name="No", last_name="Email")
        add_to_target_list(self.good, self.target_list)
        add_to_target_list(self.opted_out, self.target_list, opted_out=True)
        add_to_target_list(self.no_email, self.target_list)

        self.template = EmailTemplate.objects.create(
            name="Blast", subject="Hi {{ first_name }}", body="<p>Hello {{ first_name }}</p>"
        )
        self.campaign = Campaign.objects.create(name="Blast campaign")
        self.mass_email = MassEmail.objects.create(
            name="Blast",
            email_template=self.template,
            campaign=self.campaign,
            store_sent_emails=True,
        )
        self.mass_email.target_lists.add(self.target_list)

    def test_build_queue_skips_opted_out_and_missing_email(self):
        count = build_queue(self.mass_email)
        self.assertEqual(count, 1)
        self.mass_email.refresh_from_db()
        self.assertEqual(self.mass_email.status, MassEmail.Status.IN_PROCESS)

    def test_process_queue_sends_and_updates_campaign(self):
        build_queue(self.mass_email)
        sent = process_mass_email(type("Job", (), {"data": {"mass_email_id": self.mass_email.pk}})())
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["good@example.com"])

        self.mass_email.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual(self.mass_email.status, MassEmail.Status.COMPLETE)
        self.assertEqual(self.campaign.sent_count, 1)
        self.assertTrue(
            CampaignLogRecord.objects.filter(
                campaign=self.campaign, action=CampaignLogRecord.Action.SENT
            ).exists()
        )
        self.assertTrue(
            Note.objects.filter(parent_id=self.good.pk, type=Note.Type.EMAIL).exists()
        )

    def test_process_queue_without_template_fails_items(self):
        build_queue(self.mass_email)
        self.mass_email.email_template = None
        self.mass_email.save(update_fields=["email_template"])
        process_mass_email(type("Job", (), {"data": {"mass_email_id": self.mass_email.pk}})())
        self.assertEqual(
            self.mass_email.queue_items.get().status,
            EmailQueueItem.Status.FAILED,
        )


class LeadCaptureTests(TestCase):
    def setUp(self):
        self.target_list = TargetList.objects.create(name="Web leads")
        self.capture = LeadCapture.objects.create(
            name="Website form",
            target_list=self.target_list,
            source="Web Site",
        )

    def test_capture_creates_lead_and_adds_to_target_list(self):
        response = self.client.post(
            reverse("lead_capture", args=[self.capture.api_key]),
            data=json.dumps(
                {
                    "first_name": "Web",
                    "last_name": "Visitor",
                    "email_address": "web@example.com",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get(last_name="Visitor")
        self.assertEqual(lead.source, "Web Site")
        self.assertTrue(
            TargetListMember.objects.filter(
                target_list=self.target_list, entity_id=lead.pk
            ).exists()
        )

    def test_invalid_key(self):
        response = self.client.post(
            reverse("lead_capture", args=["nope"]),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_required_field(self):
        response = self.client.post(
            reverse("lead_capture", args=[self.capture.api_key]),
            data=json.dumps({"first_name": "Only"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

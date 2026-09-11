import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from omacrm.core.models import (
    Attachment,
    CurrencyRate,
    CustomField,
    DynamicRecord,
    Email,
    Layout,
    RecordLink,
    SavedFilter,
    User,
    WebhookQueueItem,
)
from omacrm.crm.models import (
    Account,
    Attendance,
    Campaign,
    CampaignLogRecord,
    Case,
    Contact,
    Document,
    EmailQueueItem,
    KnowledgeBaseArticle,
    Lead,
    MassEmail,
    Meeting,
    Opportunity,
    TargetListMember,
    Task,
)

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SeedDemoTests(TestCase):
    def _seed(self, **kwargs):
        call_command("seed_demo", reset=True, verbosity=0, **kwargs)

    def test_seed_creates_rich_dataset_and_invariants(self):
        self._seed()

        self.assertGreaterEqual(Account.objects.count(), 13)
        self.assertGreaterEqual(Contact.objects.count(), 21)
        self.assertEqual(Lead.objects.count(), 12)
        self.assertEqual(Opportunity.objects.filter(stage="Closed Won").count(), 2)
        self.assertEqual(Opportunity.objects.filter(stage="Closed Lost").count(), 1)
        self.assertGreaterEqual(Task.objects.count(), 17)
        self.assertGreaterEqual(Case.objects.count(), 8)
        self.assertEqual(KnowledgeBaseArticle.objects.count(), 7)
        self.assertEqual(Document.objects.count(), 7)
        self.assertEqual(Campaign.objects.count(), 3)
        self.assertEqual(MassEmail.objects.count(), 2)

        statuses = set(Attendance.objects.values_list("status", flat=True))
        self.assertTrue({"Accepted", "Tentative", "Declined"} <= statuses)
        self.assertGreaterEqual(Meeting.objects.filter(recurrence_uid__gt="").count(), 4)
        self.assertGreaterEqual(CampaignLogRecord.objects.count(), 20)
        self.assertGreaterEqual(EmailQueueItem.objects.count(), 7)
        self.assertGreaterEqual(WebhookQueueItem.objects.count(), 3)
        self.assertEqual(CurrencyRate.objects.count(), 36)
        self.assertEqual(DynamicRecord.objects.filter(entity_type="Project").count(), 3)
        self.assertGreaterEqual(RecordLink.objects.count(), 9)
        project = DynamicRecord.objects.filter(entity_type="Project").first()
        self.assertIn("code", project.custom_data)
        self.assertTrue(project.custom_data["site_address"]["city"])
        self.assertTrue(project.custom_data["files"])

        candidates = DynamicRecord.objects.filter(entity_type="Candidate")
        self.assertEqual(candidates.count(), 2)
        self.assertTrue(candidates.filter(name="Ada Lovelace").exists())
        self.assertGreaterEqual(CustomField.objects.count(), 6)
        self.assertGreaterEqual(Layout.objects.count(), 2)
        self.assertGreaterEqual(SavedFilter.objects.count(), 3)
        self.assertGreaterEqual(TargetListMember.objects.count(), 15)
        self.assertGreaterEqual(Attachment.objects.count(), 3)

        campaign = Campaign.objects.get(name="September Newsletter")
        self.assertEqual(campaign.sent_count, 8)
        self.assertEqual(campaign.opened_count, 5)
        self.assertEqual(campaign.clicked_count, 3)
        self.assertEqual(campaign.bounced_count, 1)
        self.assertGreater(campaign.revenue, 0)

        thread = Email.objects.filter(thread_id="<demo-thread-1@example.com>")
        self.assertEqual(thread.count(), 3)
        self.assertTrue(thread.exclude(parent_email=None).exists())

        self.assertTrue(
            Lead.objects.filter(custom_data__has_key="lead_score").exists()
        )
        self.assertTrue(Contact.objects.filter(portal_user__isnull=False).exists())
        self.assertTrue(
            Document.objects.filter(
                accounts__name="TechBrasil Sistemas", status="Active"
            ).exists()
        )
        for user_name in ("ana.souza", "bruno.almeida", "carla.mendes", "api.bot"):
            self.assertTrue(User.objects.filter(user_name=user_name).exists())

    def test_seed_without_reset_keeps_existing_data(self):
        self._seed()
        account_count = Account.objects.count()
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Account.objects.count(), account_count)

    def test_reset_is_stable_and_preserves_logins(self):
        self._seed()
        first = {
            "accounts": Account.objects.count(),
            "contacts": Contact.objects.count(),
            "opportunities": Opportunity.objects.count(),
            "tasks": Task.objects.count(),
            "campaigns": Campaign.objects.count(),
            "projects": DynamicRecord.objects.filter(entity_type="Project").count(),
        }

        self._seed()
        second = {
            "accounts": Account.objects.count(),
            "contacts": Contact.objects.count(),
            "opportunities": Opportunity.objects.count(),
            "tasks": Task.objects.count(),
            "campaigns": Campaign.objects.count(),
            "projects": DynamicRecord.objects.filter(entity_type="Project").count(),
        }
        self.assertEqual(first, second)

        for user_name in ("admin", "demo", "portal"):
            self.assertTrue(User.objects.filter(user_name=user_name).exists())
        portal = User.objects.get(user_name="portal")
        self.assertTrue(portal.check_password("portal12345"))

import hashlib
import hmac
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase

from omacrm.core.models import Webhook, WebhookQueueItem
from omacrm.core.services.webhooks import MAX_ATTEMPTS, process_webhooks
from omacrm.crm.models import Contact


class WebhookTests(TestCase):
    def setUp(self):
        self.webhook = Webhook.objects.create(
            name="Contact create",
            entity_type="Contact",
            event="create",
            url="https://example.com/hook",
            secret="s3cret",
        )

    def test_create_enqueues_payload(self):
        Contact.objects.create(first_name="Jane", last_name="Hook")
        item = WebhookQueueItem.objects.get(webhook=self.webhook)
        self.assertEqual(item.status, WebhookQueueItem.Status.PENDING)
        self.assertEqual(item.payload["entity_type"], "Contact")
        self.assertEqual(item.payload["event"], "create")
        self.assertEqual(item.payload["data"]["last_name"], "Hook")

    def test_soft_delete_enqueues_delete_event(self):
        delete_webhook = Webhook.objects.create(
            name="Contact delete",
            entity_type="Contact",
            event="delete",
            url="https://example.com/delete",
        )
        contact = Contact.objects.create(first_name="Jane", last_name="Hook")
        contact.delete()
        self.assertTrue(
            WebhookQueueItem.objects.filter(
                webhook=delete_webhook, payload__event="delete"
            ).exists()
        )

    def test_update_event(self):
        contact = Contact.objects.create(first_name="Jane", last_name="Hook")
        webhook = Webhook.objects.create(
            name="Contact update",
            entity_type="Contact",
            event="update",
            url="https://example.com/update",
        )
        contact.first_name = "Janet"
        contact.save()
        self.assertTrue(
            WebhookQueueItem.objects.filter(webhook=webhook).exists()
        )

    @patch("omacrm.core.services.webhooks.urllib.request.urlopen")
    def test_successful_delivery(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.status = 200

        Contact.objects.create(first_name="Jane", last_name="Hook")
        delivered = process_webhooks(None)

        self.assertEqual(delivered, 1)
        item = WebhookQueueItem.objects.get(webhook=self.webhook)
        self.assertEqual(item.status, WebhookQueueItem.Status.SENT)
        self.assertEqual(item.response_code, 200)
        self.assertIsNotNone(item.delivered_at)

        request = urlopen.call_args.args[0]
        expected_signature = hmac.new(
            b"s3cret", request.data, hashlib.sha256
        ).hexdigest()
        self.assertEqual(
            request.get_header("X-webhook-signature"), expected_signature
        )

    @patch(
        "omacrm.core.services.webhooks.urllib.request.urlopen",
        side_effect=URLError("connection refused"),
    )
    def test_failure_marks_failed_after_max_attempts(self, urlopen):
        Contact.objects.create(first_name="Jane", last_name="Hook")
        for _ in range(MAX_ATTEMPTS):
            process_webhooks(None)

        item = WebhookQueueItem.objects.get(webhook=self.webhook)
        self.assertEqual(item.status, WebhookQueueItem.Status.FAILED)
        self.assertEqual(item.attempts, MAX_ATTEMPTS)
        self.assertIn("connection refused", item.last_error)

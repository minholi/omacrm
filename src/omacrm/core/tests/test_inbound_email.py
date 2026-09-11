from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from omacrm.core.admin.email import EmailAccountForm
from omacrm.core.models import Email, EmailAccount, User
from omacrm.core.services.crypto import decrypt, encrypt
from omacrm.core.services.inbound_email import (
    fetch_account,
    fetch_inbound_email,
    import_message,
)
from omacrm.crm.models import Contact


def build_raw_message(
    subject="Hello",
    sender="jane@example.com",
    to="ops@example.com",
    message_id=None,
    plain="Plain body",
    html=None,
):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message["Message-ID"] = message_id or make_msgid()
    message["Date"] = formatdate(localtime=True)
    message.set_content(plain)
    if html:
        message.add_alternative(html, subtype="html")
    return message.as_bytes()


class CryptoServiceTests(TestCase):
    def test_encrypt_decrypt_round_trip(self):
        token = encrypt("s3cret")
        self.assertNotEqual(token, "s3cret")
        self.assertEqual(decrypt(token), "s3cret")

    def test_decrypt_invalid_returns_empty(self):
        self.assertEqual(decrypt("not-a-token"), "")
        self.assertEqual(decrypt(""), "")


class ImportMessageTests(TestCase):
    def setUp(self):
        self.account = EmailAccount.objects.create(
            name="Support", imap_host="imap.example.com"
        )

    def test_import_creates_email(self):
        record = import_message(
            self.account, build_raw_message(html="<p>HTML body</p>")
        )
        self.assertIsNotNone(record)
        record.refresh_from_db()
        self.assertEqual(record.subject, "Hello")
        self.assertEqual(record.from_address, "jane@example.com")
        self.assertEqual(record.to_address, "ops@example.com")
        self.assertEqual(record.status, Email.Status.ARCHIVED)
        self.assertFalse(record.is_read)
        self.assertTrue(record.is_html)
        self.assertIn("HTML body", record.body)
        self.assertIn("Plain body", record.body_plain)

    def test_duplicate_message_is_skipped(self):
        raw = build_raw_message(message_id="<dup@example.com>")
        first = import_message(self.account, raw)
        second = import_message(self.account, raw)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Email.objects.count(), 1)

    def test_parent_linked_by_sender_email(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", email_address="jane@example.com"
        )
        record = import_message(self.account, build_raw_message())
        self.assertEqual(record.parent, contact)

    def test_default_assignee_applied(self):
        user = User.objects.create_user("mailer", "mailer@example.com", "pw")
        self.account.default_assigned_user = user
        self.account.save()
        record = import_message(self.account, build_raw_message())
        self.assertEqual(record.assigned_user, user)


class FetchAccountTests(TestCase):
    def setUp(self):
        self.account = EmailAccount.objects.create(
            name="Fetch", imap_host="imap.example.com", imap_username="user"
        )
        self.account.set_password("secret")
        self.account.save()

    def _fake_client(self, raw):
        client = MagicMock()
        client.login.return_value = ("OK", [b"Logged in"])
        client.select.return_value = ("OK", [b"1"])
        client.search.return_value = ("OK", [b"1"])
        client.fetch.return_value = ("OK", [(b"1 (BODY[] {123}", raw)])
        client.store.return_value = ("OK", [b"1"])
        client.logout.return_value = ("BYE", [b""])
        return client

    def test_fetch_account_imports_and_updates_timestamp(self):
        client = self._fake_client(build_raw_message())
        with patch(
            "omacrm.core.services.inbound_email.imaplib.IMAP4_SSL",
            return_value=client,
        ):
            imported = fetch_account(self.account)

        self.assertEqual(imported, 1)
        self.assertEqual(Email.objects.count(), 1)
        client.login.assert_called_once_with("user", "secret")
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.last_fetched_at)

    def test_job_iterates_active_accounts(self):
        EmailAccount.objects.create(
            name="Inactive", imap_host="imap.example.com", is_active=False
        )
        with patch(
            "omacrm.core.services.inbound_email.fetch_account", return_value=2
        ) as mocked:
            total = fetch_inbound_email(None)
        self.assertEqual(total, 2)
        self.assertEqual(mocked.call_count, 1)


class EmailAccountFormTests(TestCase):
    def test_password_is_encrypted(self):
        form = EmailAccountForm(
            data={
                "name": "Account",
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "imap_ssl": "on",
                "imap_username": "user",
                "password": "topsecret",
                "folder": "INBOX",
                "unseen_only": "on",
                "is_active": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        self.assertNotEqual(account.imap_password, "topsecret")
        self.assertEqual(account.get_password(), "topsecret")

    def test_blank_password_keeps_current(self):
        account = EmailAccount.objects.create(name="Keep", imap_host="imap.example.com")
        account.set_password("original")
        account.save()

        form = EmailAccountForm(
            data={
                "name": "Keep",
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "imap_ssl": "on",
                "imap_username": "user",
                "password": "",
                "folder": "INBOX",
                "unseen_only": "on",
                "is_active": "on",
            },
            instance=account,
        )
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        self.assertEqual(account.get_password(), "original")


class EmailAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("mail-admin2", "ma2@example.com", "pw")
        self.client.force_login(self.admin)

    def test_changelists_and_add_form_render(self):
        for url in (
            "/admin/core/email/",
            "/admin/core/emailaccount/",
            "/admin/core/emailaccount/add/",
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

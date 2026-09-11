import tempfile
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from omacrm.core.admin.email import EmailAccountForm
from omacrm.core.models import Attachment, Email, EmailAccount, User
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
    in_reply_to=None,
    references=None,
):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message["Message-ID"] = message_id or make_msgid()
    message["Date"] = formatdate(localtime=True)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(plain)
    if html:
        message.add_alternative(html, subtype="html")
    return message.as_bytes()


def build_raw_message_with_attachment(
    filename="report.txt", content=b"file-content", message_id=None
):
    message = EmailMessage()
    message["Subject"] = "With attachment"
    message["From"] = "jane@example.com"
    message["To"] = "ops@example.com"
    message["Message-ID"] = message_id or make_msgid()
    message["Date"] = formatdate(localtime=True)
    message.set_content("See attached")
    message.add_attachment(
        content, maintype="text", subtype="plain", filename=filename
    )
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

    def test_folder_recorded(self):
        record = import_message(self.account, build_raw_message(), folder="Sent")
        self.assertEqual(record.folder, "Sent")
        record = import_message(self.account, build_raw_message(), folder="")
        self.assertEqual(record.folder, "INBOX")

    def test_reply_threading(self):
        parent = import_message(
            self.account, build_raw_message(message_id="<parent@example.com>")
        )
        reply = import_message(
            self.account,
            build_raw_message(
                sender="bob@example.com",
                message_id="<reply@example.com>",
                in_reply_to="<parent@example.com>",
                references="<parent@example.com>",
            ),
        )
        self.assertEqual(reply.parent_email, parent)
        self.assertEqual(reply.thread_id, parent.thread_id)
        self.assertEqual(parent.thread_id, "<parent@example.com>")

    def test_reply_inherits_crm_parent(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", email_address="jane@example.com"
        )
        parent = import_message(
            self.account, build_raw_message(message_id="<p2@example.com>")
        )
        self.assertEqual(parent.parent, contact)
        reply = import_message(
            self.account,
            build_raw_message(
                sender="bob@example.com",
                message_id="<r2@example.com>",
                in_reply_to="<p2@example.com>",
            ),
        )
        self.assertEqual(reply.parent, contact)
        self.assertEqual(reply.parent_email, parent)


MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AttachmentImportTests(TestCase):
    def setUp(self):
        self.account = EmailAccount.objects.create(
            name="Files", imap_host="imap.example.com"
        )

    def test_attachment_imported_and_linked(self):
        from django.contrib.contenttypes.models import ContentType

        record = import_message(
            self.account, build_raw_message_with_attachment()
        )
        attachment = Attachment.objects.get(
            related_type=ContentType.objects.get_for_model(
                record, for_concrete_model=False
            ),
            related_id=record.pk,
        )
        self.assertEqual(attachment.name, "report.txt")
        self.assertEqual(attachment.mime_type, "text/plain")
        self.assertEqual(attachment.file.read(), b"file-content")


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

    def test_fetch_polls_multiple_folders(self):
        self.account.folder = "INBOX, Sent"
        self.account.save()
        client = MagicMock()
        client.login.return_value = ("OK", [b"Logged in"])
        client.select.side_effect = [("OK", [b"1"]), ("OK", [b"1"])]
        client.search.side_effect = [("OK", [b"1"]), ("OK", [b"2"])]
        client.fetch.side_effect = [
            ("OK", [(b"1", build_raw_message(message_id="<f1@example.com>"))]),
            ("OK", [(b"2", build_raw_message(message_id="<f2@example.com>"))]),
        ]
        client.store.return_value = ("OK", [b"1"])
        client.logout.return_value = ("BYE", [b""])

        with patch(
            "omacrm.core.services.inbound_email.imaplib.IMAP4_SSL",
            return_value=client,
        ):
            imported = fetch_account(self.account)

        self.assertEqual(imported, 2)
        client.select.assert_any_call("INBOX")
        client.select.assert_any_call("Sent")
        self.assertEqual(
            Email.objects.get(message_id="<f1@example.com>").folder, "INBOX"
        )
        self.assertEqual(
            Email.objects.get(message_id="<f2@example.com>").folder, "Sent"
        )

    def test_fetch_skips_unopenable_folder(self):
        self.account.folder = "Bad, INBOX"
        self.account.save()
        client = MagicMock()
        client.login.return_value = ("OK", [b"Logged in"])
        client.select.side_effect = [RuntimeError("no such folder"), ("OK", [b"1"])]
        client.search.return_value = ("OK", [b"1"])
        client.fetch.return_value = (
            "OK",
            [(b"1", build_raw_message(message_id="<ok@example.com>"))],
        )
        client.store.return_value = ("OK", [b"1"])
        client.logout.return_value = ("BYE", [b""])

        with patch(
            "omacrm.core.services.inbound_email.imaplib.IMAP4_SSL",
            return_value=client,
        ):
            imported = fetch_account(self.account)

        self.assertEqual(imported, 1)
        self.assertTrue(Email.objects.filter(message_id="<ok@example.com>").exists())


class EmailAccountFolderTests(TestCase):
    def test_folder_names_parsing(self):
        account = EmailAccount.objects.create(
            name="Folders", imap_host="imap.example.com", folder="INBOX, Sent; Archive"
        )
        self.assertEqual(account.folder_names, ["INBOX", "Sent", "Archive"])

        account.folder = ""
        self.assertEqual(account.folder_names, ["INBOX"])


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

    def test_email_detail_renders(self):
        email = Email.objects.create(subject="Hello")
        response = self.client.get(f"/admin/core/email/{email.pk}/change/")
        self.assertEqual(response.status_code, 200)

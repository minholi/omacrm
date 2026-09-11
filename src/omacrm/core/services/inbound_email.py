"""Inbound email: poll IMAP mailboxes and import messages as Email records."""

import email
import imaplib
import logging
import os
import re
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from omacrm.core.models import Attachment, Email, EmailAccount
from omacrm.core.services.jobs import jobs

logger = logging.getLogger(__name__)

_MESSAGE_ID_RE = re.compile(r"<[^>]+>")


def _decode(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001 - malformed headers
        return str(value)


def _address_list(value) -> str:
    return ", ".join(
        address.lower() for _name, address in getaddresses([value or ""]) if address
    )


def _first_address(value) -> str:
    addresses = getaddresses([value or ""])
    return addresses[0][1].lower() if addresses else ""


def _extract_bodies(message) -> tuple[str, str]:
    plain: list[str] = []
    html: list[str] = []

    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        disposition = str(part.get("Content-Disposition") or "")
        if "attachment" in disposition:
            continue
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        (plain if content_type == "text/plain" else html).append(text)

    return "\n".join(plain).strip(), "\n".join(html).strip()


def _extract_attachments(message) -> list[tuple[str, str, bytes]]:
    attachments = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disposition = str(part.get("Content-Disposition") or "")
        filename = _decode(part.get_filename())
        if not filename and "attachment" not in disposition:
            continue
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001 - malformed part
            continue
        if not payload:
            continue
        safe_name = os.path.basename(filename).strip() or "attachment"
        attachments.append((safe_name[:255], part.get_content_type(), payload))
    return attachments


def _thread_candidates(message) -> list[str]:
    """Candidate parent Message-IDs, direct parent last."""

    references = _MESSAGE_ID_RE.findall(message.get("References") or "")
    in_reply_to = _MESSAGE_ID_RE.findall(message.get("In-Reply-To") or "")
    ordered: list[str] = []
    for message_id in references + in_reply_to:
        message_id = message_id.strip()
        if message_id and message_id not in ordered:
            ordered.append(message_id)
    return ordered


def find_thread_parent(message):
    """Find the stored Email this message replies to, if any."""

    candidates = _thread_candidates(message)
    if not candidates:
        return None

    rank = {message_id: index for index, message_id in enumerate(candidates)}
    matches = list(Email.objects.filter(message_id__in=candidates))
    if not matches:
        return None
    return max(matches, key=lambda item: rank.get(item.message_id, -1))


def match_parent(from_address: str):
    """Link a message to a CRM record by sender email, when possible."""

    if not from_address:
        return None

    from omacrm.core.metadata.registry import registry

    for entity_type in ("Contact", "Lead", "Account"):
        if not registry.has(entity_type):
            continue
        model = registry.model_for(entity_type)
        field_names = {field.name for field in model._meta.get_fields()}
        if "email_address" not in field_names:
            continue
        match = model.objects.filter(email_address__iexact=from_address).first()
        if match is not None:
            return match
    return None


def import_message(account: EmailAccount, raw: bytes, folder: str = ""):
    """Store a raw RFC822 message as an Email; ``None`` when duplicated."""

    message = email.message_from_bytes(raw)
    message_id = (message.get("Message-ID") or "").strip()
    if message_id and Email.all_objects.filter(message_id=message_id).exists():
        return None

    plain, html = _extract_bodies(message)

    date_sent = None
    if message.get("Date"):
        try:
            date_sent = parsedate_to_datetime(message.get("Date"))
        except (TypeError, ValueError):
            date_sent = None
        if date_sent is not None and timezone.is_naive(date_sent):
            date_sent = timezone.make_aware(date_sent)

    from_address = _first_address(message.get("From"))
    record = Email(
        subject=_decode(message.get("Subject")),
        body=html or plain,
        body_plain=plain,
        is_html=bool(html),
        from_address=from_address,
        to_address=_address_list(message.get("To")),
        cc_address=_address_list(message.get("Cc")),
        bcc_address=_address_list(message.get("Bcc")),
        message_id=message_id,
        folder=folder or account.folder_names[0],
        thread_id=message_id,
        date_sent=date_sent,
        status=Email.Status.ARCHIVED,
        is_read=False,
    )
    if account.default_assigned_user_id:
        record.assigned_user = account.default_assigned_user
    record.save()

    update_fields: list[str] = []
    parent = match_parent(from_address)
    thread_parent = find_thread_parent(message)
    if parent is not None:
        record.parent = parent
        update_fields += ["parent_type", "parent_id"]
    elif thread_parent is not None and thread_parent.parent_id:
        record.parent = thread_parent.parent
        update_fields += ["parent_type", "parent_id"]
    if thread_parent is not None:
        record.parent_email = thread_parent
        record.thread_id = thread_parent.thread_id or thread_parent.message_id
        update_fields += ["parent_email", "thread_id"]
    if update_fields:
        record.save(update_fields=update_fields)

    for name, mime_type, payload in _extract_attachments(message):
        Attachment(
            name=name,
            mime_type=mime_type,
            file=ContentFile(payload, name=name),
            related=record,
        ).save()

    return record


def fetch_account(account: EmailAccount, limit: int = 50) -> int:
    """Fetch messages from an IMAP account; returns the number imported."""

    if account.imap_ssl:
        client = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    else:
        client = imaplib.IMAP4(account.imap_host, account.imap_port)

    imported = 0
    try:
        client.login(account.imap_username, account.get_password())

        for folder in account.folder_names:
            try:
                status, _data = client.select(folder)
            except Exception:  # noqa: BLE001 - try the next folder
                logger.exception("Cannot open folder %s of %s", folder, account.name)
                continue
            if status != "OK":
                logger.warning("Cannot open folder %s of %s", folder, account.name)
                continue

            criteria = "UNSEEN" if account.unseen_only else "ALL"
            status, data = client.search(None, criteria)
            if status != "OK":
                continue

            message_ids = data[0].split()[-limit:]
            for message_id in message_ids:
                status, payload = client.fetch(message_id, "(BODY.PEEK[])")
                if status != "OK" or not payload:
                    continue
                raw = None
                for part in payload:
                    if isinstance(part, tuple) and len(part) > 1:
                        raw = part[1]
                        break
                if not raw:
                    continue
                if import_message(account, raw, folder=folder) is not None:
                    imported += 1
                    try:
                        client.store(message_id, "+FLAGS", "(\\Seen)")
                    except Exception:  # noqa: BLE001 - optional
                        pass

        account.last_fetched_at = timezone.now()
        account.save(update_fields=["last_fetched_at"])
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001 - optional
            pass

    return imported


@jobs.register("core.fetch_inbound_email", name="Fetch inbound email accounts")
def fetch_inbound_email(job) -> int:
    total = 0
    for account in EmailAccount.objects.filter(is_active=True):
        try:
            total += fetch_account(account)
        except Exception:  # noqa: BLE001 - keep processing other accounts
            logger.exception("Failed to fetch email account %s", account.name)
    return total

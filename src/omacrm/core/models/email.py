from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models.base import AuditMixin


class Email(AuditMixin, models.Model):
    """An inbound or outbound email message."""

    class Status(models.TextChoices):
        DRAFT = "Draft", _("Draft")
        SENDING = "Sending", _("Sending")
        SENT = "Sent", _("Sent")
        ARCHIVED = "Archived", _("Archived")
        FAILED = "Failed", _("Failed")

    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    body_plain = models.TextField(blank=True, default="")
    is_html = models.BooleanField(default=False)
    from_address = models.EmailField(blank=True, default="", db_index=True)
    to_address = models.TextField(blank=True, default="")
    cc_address = models.TextField(blank=True, default="")
    bcc_address = models.TextField(blank=True, default="")
    message_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    folder = models.CharField(
        max_length=255, blank=True, default="", help_text=_("IMAP folder it came from.")
    )
    thread_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    parent_email = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    date_sent = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ARCHIVED
    )
    is_read = models.BooleanField(default=False, db_index=True)

    parent_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    parent_id = models.PositiveBigIntegerField(null=True, blank=True)
    parent = GenericForeignKey("parent_type", "parent_id", for_concrete_model=False)

    class Meta:
        ordering = ["-date_sent", "-created_at"]
        verbose_name = "Email"

    def __str__(self):
        return self.subject or self.message_id or f"Email #{self.pk}"


class EmailAccount(models.Model):
    """An IMAP mailbox polled by the inbound-email job."""

    name = models.CharField(max_length=100, unique=True)
    email_address = models.EmailField(blank=True, default="")
    imap_host = models.CharField(max_length=255)
    imap_port = models.PositiveIntegerField(default=993)
    imap_ssl = models.BooleanField(default=True)
    imap_username = models.CharField(max_length=255, blank=True, default="")
    imap_password = models.CharField(max_length=255, blank=True, default="")
    folder = models.CharField(
        max_length=255,
        blank=True,
        default="INBOX",
        help_text=_("Comma-separated IMAP folders to poll."),
    )
    unseen_only = models.BooleanField(
        default=True, help_text=_("Fetch only unread messages.")
    )
    is_active = models.BooleanField(default=True)
    default_assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Email Account"
        verbose_name_plural = "Email Accounts"

    def __str__(self):
        return self.name

    @property
    def folder_names(self) -> list[str]:
        raw = (self.folder or "INBOX").replace(";", ",")
        names = [name.strip() for name in raw.split(",") if name.strip()]
        return names or ["INBOX"]

    def set_password(self, raw: str) -> None:
        from omacrm.core.services.crypto import encrypt

        self.imap_password = encrypt(raw)

    def get_password(self) -> str:
        from omacrm.core.services.crypto import decrypt

        return decrypt(self.imap_password)

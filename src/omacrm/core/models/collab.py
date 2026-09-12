import mimetypes
import os

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Attachment(models.Model):
    file = models.FileField(upload_to="attachments/%Y/%m/")
    name = models.CharField(max_length=255, blank=True, default="")
    mime_type = models.CharField(max_length=100, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    related_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    related_id = models.PositiveBigIntegerField(null=True, blank=True)
    related = GenericForeignKey("related_type", "related_id", for_concrete_model=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"Attachment #{self.pk}"

    def save(self, *args, **kwargs):
        if self.file:
            if not self.name:
                self.name = os.path.basename(self.file.name)
            try:
                self.size = self.file.size
            except (OSError, ValueError):
                pass
            if not self.mime_type:
                self.mime_type = mimetypes.guess_type(self.file.name)[0] or ""
        if self.created_by_id is None:
            from omacrm.core.services.context import get_current_user

            user = get_current_user()
            if user is not None:
                self.created_by = user
        super().save(*args, **kwargs)


class Note(models.Model):
    """Stream / activity feed entry (posts and system audit notes)."""

    class Type(models.TextChoices):
        POST = "Post", "Post"
        CREATE = "Create", "Create"
        UPDATE = "Update", "Update"
        DELETE = "Delete", "Delete"
        ASSIGN = "Assign", "Assign"
        RELATE = "Relate", "Relate"
        UNRELATE = "Unrelate", "Unrelate"
        EMAIL = "Email", "Email"

    type = models.CharField(max_length=20, choices=Type.choices, default=Type.POST)
    post = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    parent_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    parent_id = models.PositiveBigIntegerField(null=True, blank=True)
    parent = GenericForeignKey("parent_type", "parent_id", for_concrete_model=False)
    related_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    related_id = models.PositiveBigIntegerField(null=True, blank=True)
    related = GenericForeignKey("related_type", "related_id", for_concrete_model=False)
    is_internal = models.BooleanField(default=False)
    attachments = models.ManyToManyField(Attachment, blank=True, related_name="notes")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notes",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.post[:50] or f"{self.type} note #{self.pk}"

    @property
    def parent_display(self):
        """Safe rendering of the generic parent for lists/dashboards."""

        try:
            parent = self.parent
        except Exception:  # noqa: BLE001 - stale content type
            return ""
        return str(parent) if parent is not None else ""

    @property
    def reaction_summary(self) -> str:
        from django.db.models import Count

        rows = (
            self.reactions.values("emoji")
            .annotate(total=Count("id"))
            .order_by("-total", "emoji")
        )
        return " · ".join(f"{row['emoji']} {row['total']}" for row in rows)


class UserReaction(models.Model):
    """An emoji reaction by a user on a stream note."""

    note = models.ForeignKey(
        Note, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="note_reactions",
    )
    emoji = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("note", "user", "emoji")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.emoji} by {self.user}"


class StarSubscription(models.Model):
    """A user's favourite (star) on one record of any entity type.

    The record is identified by its metadata entity type plus primary key, so
    runtime custom entities work exactly like built-in ones. The unique
    constraint keeps one star per user and record.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="star_subscriptions",
    )
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "entity_type", "entity_id")]
        indexes = [
            models.Index(fields=["user", "entity_type"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id} starred by {self.user}"


class StreamSubscription(models.Model):
    """A user following one record (gets stream notifications about it)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stream_subscriptions",
    )
    entity_type = models.CharField(max_length=64)
    entity_id = models.PositiveBigIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user", "entity_type"]),
        ]

    def __str__(self):
        return f"{self.user} follows {self.entity_type}:{self.entity_id}"


class StreamEvent(models.Model):
    """A pending real-time stream update for one user (consumed over SSE)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stream_events",
    )
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="events")
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.message


class Notification(models.Model):
    class Type(models.TextChoices):
        ASSIGNMENT = "Assignment", "Assignment"
        MENTION = "Mention", "Mention"
        STREAM = "Stream", "Stream"
        SYSTEM = "System", "System"
        EMAIL = "Email", "Email"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SYSTEM)
    read = models.BooleanField(default=False, db_index=True)
    message = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    related_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    related_id = models.PositiveBigIntegerField(null=True, blank=True)
    related = GenericForeignKey("related_type", "related_id", for_concrete_model=False)
    email_is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} -> {self.user}"

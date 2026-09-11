from django.db import models


class Webhook(models.Model):
    class Event(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"

    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=64)
    event = models.CharField(max_length=20, choices=Event.choices)
    url = models.URLField()
    secret = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Optional secret used to sign the payload (HMAC-SHA256).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_type", "event", "name"]
        unique_together = [("entity_type", "event", "url")]

    def __str__(self):
        return f"{self.entity_type}.{self.event} -> {self.url}"


class WebhookQueueItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        SENT = "Sent", "Sent"
        FAILED = "Failed", "Failed"

    webhook = models.ForeignKey(
        Webhook, on_delete=models.CASCADE, related_name="queue_items"
    )
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.webhook} ({self.status})"

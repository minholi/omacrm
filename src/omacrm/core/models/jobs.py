from django.db import models
from django.utils import timezone


class Job(models.Model):
    """A queued unit of background work."""

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        RUNNING = "Running", "Running"
        SUCCESS = "Success", "Success"
        FAILED = "Failed", "Failed"

    name = models.CharField(max_length=255)
    class_name = models.CharField(max_length=255)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    queue = models.CharField(max_length=32, default="default", db_index=True)
    execute_time = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["execute_time", "id"]

    def __str__(self):
        return f"{self.name} ({self.status})"


class ScheduledJob(models.Model):
    name = models.CharField(max_length=255, unique=True)
    job = models.CharField(max_length=255, help_text="Registered job key")
    scheduling = models.CharField(max_length=64, help_text="Cron expression")
    data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_run = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ScheduledJobLog(models.Model):
    scheduled_job = models.ForeignKey(
        ScheduledJob, on_delete=models.CASCADE, related_name="logs"
    )
    status = models.CharField(max_length=32, blank=True, default="")
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.scheduled_job} @ {self.created_at:%Y-%m-%d %H:%M}"

from django.conf import settings
from django.db import models


class SavedFilter(models.Model):
    """A per-user, per-entity set of changelist query parameters."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_filters",
    )
    entity_type = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "entity_type", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.entity_type})"

from django.db import models


class PortalRole(models.Model):
    """Access rules for customer-portal users.

    ``data`` maps portal entities to levels, e.g.
    ``{"Case": {"read": "own", "create": "yes"}}``. Portal users without any
    role get sensible defaults (own cases, published KB articles).
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

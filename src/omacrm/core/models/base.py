from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from omacrm.core.managers import SoftDeleteManager


class CustomDataMixin(models.Model):
    """Adds the JSON payload used to store custom-field values."""

    custom_data = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class AuditMixin(CustomDataMixin):
    """Audit columns, assignment/teams and soft delete (no history).

    Shared by ``BaseEntity`` and by runtime-defined dynamic entities, which
    must not create historical tables.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    teams = models.ManyToManyField("core.Team", blank=True, related_name="+")
    deleted = models.BooleanField(default=False, editable=False, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted = True
        self.save(update_fields=["deleted"])

    def restore(self):
        self.deleted = False
        self.save(update_fields=["deleted"])


class BaseEntity(AuditMixin):
    """Base class for all CRM record types.

    Adds change history (django-simple-history) on top of ``AuditMixin``.
    """

    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

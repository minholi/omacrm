import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models.base import AuditMixin

CUSTOM_ENTITY_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

RESERVED_NAMES = {"User", "Team", "Role", "Preferences", "DynamicRecord", "CustomEntity"}


class CustomEntity(models.Model):
    """Admin-created entity backed by DynamicRecord (JSON storage)."""

    name = models.CharField(
        max_length=64,
        unique=True,
        help_text=_("CamelCase, e.g. Project. Used in URLs and metadata."),
    )
    label = models.CharField(max_length=120, blank=True, default="")
    label_plural = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "custom entities"

    def __str__(self):
        return self.label or self.name

    @property
    def display_label(self):
        return self.label or self.name

    @property
    def display_label_plural(self):
        return self.label_plural or f"{self.display_label}s"

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry

        if not CUSTOM_ENTITY_NAME_RE.match(self.name or ""):
            raise ValidationError(
                {
                    "name": _(
                        "Use CamelCase starting with an uppercase letter "
                        "(letters and digits only)."
                    )
                }
            )
        if self.name in RESERVED_NAMES or registry.is_builtin(self.name):
            raise ValidationError({"name": _("This name is already reserved.")})


class DynamicRecord(AuditMixin, models.Model):
    """Storage for records of runtime-defined custom entities.

    Field values live in ``custom_data`` and are described by ``CustomField``
    rows; each custom entity gets its own proxy model/admin.
    """

    entity_type = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Custom record"
        verbose_name_plural = "Custom records"

    def __str__(self):
        return self.name or f"{self.entity_type} #{self.pk}"

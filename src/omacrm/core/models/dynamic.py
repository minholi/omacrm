import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models.base import AuditMixin

CUSTOM_ENTITY_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")

RESERVED_NAMES = {"User", "Team", "Role", "Preferences", "DynamicRecord", "CustomEntity"}


class CustomEntity(models.Model):
    """Admin-created entity backed by DynamicRecord (JSON storage)."""

    class SortField(models.TextChoices):
        CREATED_AT = "created_at", _("Created At")
        MODIFIED_AT = "modified_at", _("Modified At")
        NAME = "name", _("Name")

    class SortDirection(models.TextChoices):
        ASC = "asc", _("Ascending")
        DESC = "desc", _("Descending")

    name = models.CharField(
        max_length=64,
        unique=True,
        help_text=_("CamelCase, e.g. Project. Used in URLs and metadata."),
    )
    label = models.CharField(max_length=120, blank=True, default="")
    label_plural = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    icon = models.CharField(
        max_length=64,
        blank=True,
        default="extension",
        help_text=_("Material Symbols icon name."),
    )
    color = models.CharField(
        max_length=16, blank=True, default="", help_text=_("Optional HEX color.")
    )
    show_in_menu = models.BooleanField(default=True)
    menu_order = models.PositiveSmallIntegerField(default=100)
    stream = models.BooleanField(default=True)
    sort_field = models.CharField(
        max_length=20, choices=SortField.choices, default=SortField.CREATED_AT
    )
    sort_direction = models.CharField(
        max_length=4, choices=SortDirection.choices, default=SortDirection.DESC
    )
    search_fields = models.CharField(
        max_length=255,
        blank=True,
        default="name",
        help_text=_("Comma-separated base fields used by search (name)."),
    )
    duplicate_check_fields = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=_(
            "Comma-separated base fields compared for duplicates (name)."
        ),
    )
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

    @property
    def ordering(self) -> list[str]:
        prefix = "-" if self.sort_direction == self.SortDirection.DESC else ""
        return [f"{prefix}{self.sort_field}"]

    @staticmethod
    def _split_names(value: str) -> list[str]:
        return [item.strip() for item in (value or "").split(",") if item.strip()]

    @property
    def search_field_list(self) -> list[str]:
        return self._split_names(self.search_fields) or ["name"]

    @property
    def duplicate_field_list(self) -> list[str]:
        return self._split_names(self.duplicate_check_fields)

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

        allowed = {"name"}
        invalid_search = set(self.search_field_list) - allowed
        if invalid_search:
            raise ValidationError(
                {
                    "search_fields": _(
                        "Unsupported field(s): %(fields)s (only base fields such "
                        "as name are supported)."
                    )
                    % {"fields": ", ".join(sorted(invalid_search))}
                }
            )
        invalid_duplicate = set(self.duplicate_field_list) - allowed
        if invalid_duplicate:
            raise ValidationError(
                {
                    "duplicate_check_fields": _(
                        "Unsupported field(s): %(fields)s (only base fields such "
                        "as name are supported)."
                    )
                    % {"fields": ", ".join(sorted(invalid_duplicate))}
                }
            )

    def save(self, *args, **kwargs):
        if self.pk is None and not self.icon:
            self.icon = "extension"
        super().save(*args, **kwargs)


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

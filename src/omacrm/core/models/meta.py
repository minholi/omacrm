import re

from django.core.exceptions import ValidationError
from django.db import models

CUSTOM_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class CustomField(models.Model):
    """A user-defined field layered on top of a built-in entity type.

    Values are stored in the target record's ``custom_data`` JSON payload and
    described through the metadata registry.
    """

    class FieldType(models.TextChoices):
        VARCHAR = "varchar", "Varchar"
        TEXT = "text", "Text"
        ENUM = "enum", "Enum"
        MULTI_ENUM = "multiEnum", "Multi enum"
        BOOL = "bool", "Bool"
        INT = "int", "Int"
        FLOAT = "float", "Float"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        EMAIL = "email", "Email"
        URL = "url", "URL"
        CURRENCY = "currency", "Currency"

    entity_type = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    label = models.CharField(max_length=120, blank=True, default="")
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    params = models.JSONField(default=dict, blank=True)
    required = models.BooleanField(default=False)
    read_only = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("entity_type", "name")]
        ordering = ["entity_type", "order", "name"]

    def __str__(self):
        return f"{self.entity_type}.{self.name}"

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry

        if not CUSTOM_FIELD_NAME_RE.match(self.name or ""):
            raise ValidationError(
                {
                    "name": "Use snake_case: lowercase letters, digits and underscores, starting with a letter."
                }
            )
        if self.entity_type and registry.has(self.entity_type):
            if self.name in registry.get(self.entity_type).fields:
                raise ValidationError(
                    {"name": "This name is already used by a built-in field."}
                )

    @property
    def display_label(self):
        return self.label or self.name.replace("_", " ").title()


class Layout(models.Model):
    """A metadata-driven admin layout (detail fieldsets, list columns, ...)."""

    entity_type = models.CharField(max_length=64)
    layout_name = models.CharField(max_length=64)
    data = models.JSONField(default=dict, blank=True)
    is_custom = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("entity_type", "layout_name")]
        ordering = ["entity_type", "layout_name"]

    def __str__(self):
        return f"{self.entity_type}:{self.layout_name}"


class CustomLink(models.Model):
    """A user-defined relationship between two entity types.

    ``link_type`` is described from the point of view of ``entity_type``:
    ``belongsTo`` (the source has one target), ``hasMany`` (the source has many
    targets) or ``manyToMany``. The reverse link is created automatically on
    ``link_entity`` under ``foreign_name``.
    """

    class LinkType(models.TextChoices):
        BELONGS_TO = "belongsTo", "Belongs to"
        HAS_MANY = "hasMany", "Has many"
        MANY_TO_MANY = "manyToMany", "Many to many"

    entity_type = models.CharField(max_length=64)
    name = models.CharField(
        max_length=64, help_text="snake_case link name on this entity."
    )
    label = models.CharField(max_length=120, blank=True, default="")
    link_type = models.CharField(max_length=20, choices=LinkType.choices)
    link_entity = models.CharField(max_length=64)
    foreign_name = models.CharField(
        max_length=64, blank=True, default="", help_text="Reverse link name."
    )
    label_foreign = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("entity_type", "name")]
        ordering = ["entity_type", "name"]

    def __str__(self):
        return f"{self.entity_type}.{self.name} -> {self.link_entity}"

    @property
    def forward_label(self):
        return self.label or self.name.replace("_", " ").title()

    @property
    def reverse_label(self):
        if self.label_foreign:
            return self.label_foreign
        return f"{self.link_entity} records"

    def save(self, *args, **kwargs):
        if not self.foreign_name:
            self.foreign_name = (
                f"{self.entity_type[:1].lower()}{self.entity_type[1:]}s"
            )
        super().save(*args, **kwargs)

    def _used_names(self, entity_type) -> set[str]:
        from omacrm.core.metadata.registry import registry

        names: set[str] = set()
        try:
            if registry.has(entity_type):
                names |= set(registry.get(entity_type).fields)
                names |= {fd.name for fd in registry.custom_fields(entity_type)}
        except Exception:  # noqa: BLE001 - DB may be unavailable during setup
            pass
        siblings = CustomLink.objects.filter(is_active=True).exclude(pk=self.pk)
        for row in siblings:
            if row.entity_type == entity_type:
                names.add(row.name)
            if row.link_entity == entity_type:
                names.add(row.foreign_name)
        return names

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry

        errors = {}
        if not CUSTOM_FIELD_NAME_RE.match(self.name or ""):
            errors["name"] = (
                "Use snake_case: lowercase letters, digits and underscores, "
                "starting with a letter."
            )
        if not CUSTOM_FIELD_NAME_RE.match(self.foreign_name or ""):
            errors["foreign_name"] = "Use snake_case, e.g. projects or accounts."
        if self.name and self.name == self.foreign_name:
            errors["foreign_name"] = "The reverse name must differ from the link name."
        if self.entity_type and not registry.has(self.entity_type):
            errors["entity_type"] = "Unknown entity type."
        if self.link_entity and not registry.has(self.link_entity):
            errors["link_entity"] = "Unknown entity type."
        if self.name in self._used_names(self.entity_type):
            errors["name"] = "This name is already used by a field or link."
        if self.foreign_name in self._used_names(self.link_entity):
            errors["foreign_name"] = "This name is already used by a field or link."
        if errors:
            raise ValidationError(errors)


class RecordLink(models.Model):
    """A stored relationship between two records of any entity types.

    Both directions are stored as separate rows (the reverse row is created by
    :mod:`omacrm.core.services.relations`), which keeps lookups uniform for
    belongsTo/hasMany/manyToMany links.
    """

    source_type = models.CharField(max_length=64, db_index=True)
    source_id = models.PositiveBigIntegerField()
    link = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, db_index=True)
    target_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ("source_type", "source_id", "link", "target_type", "target_id")
        ]
        indexes = [
            models.Index(fields=["source_type", "source_id", "link"]),
            models.Index(fields=["target_type", "target_id", "link"]),
        ]
        ordering = ["pk"]

    def __str__(self):
        return f"{self.source_type}:{self.source_id}.{self.link} -> {self.target_type}:{self.target_id}"

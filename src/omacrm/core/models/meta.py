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
    """A user-defined relationship between entity types (foundation)."""

    class LinkType(models.TextChoices):
        BELONGS_TO = "belongsTo", "Belongs to"
        HAS_MANY = "hasMany", "Has many"
        MANY_TO_MANY = "manyToMany", "Many to many"

    entity_type = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    label = models.CharField(max_length=120, blank=True, default="")
    link_type = models.CharField(max_length=20, choices=LinkType.choices)
    link_entity = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("entity_type", "name")]
        ordering = ["entity_type", "name"]

    def __str__(self):
        return f"{self.entity_type}.{self.name} -> {self.link_entity}"

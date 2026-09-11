"""Mapping of metadata field types to Django forms, widgets and filters."""

from django import forms
from django.contrib import admin
from django.utils.text import slugify

from omacrm.core.metadata.defs import FieldDef
from unfold.widgets import (
    UnfoldAdminCheckboxSelectMultipleWidget,
    UnfoldAdminDecimalFieldWidget,
    UnfoldAdminEmailInputWidget,
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminSingleDateWidget,
    UnfoldAdminSplitDateTimeWidget,
    UnfoldAdminTextInputWidget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminURLInputWidget,
    UnfoldBooleanSwitchWidget,
)

SIMPLE_TEXT_TYPES = {"varchar", "enum"}


def build_form_field(field_def: FieldDef) -> forms.Field:
    """Build an admin form field for a custom metadata field."""

    params = field_def.params or {}
    common = {
        "label": field_def.display_label,
        "required": field_def.required,
        "help_text": field_def.help_text or params.get("tooltip", ""),
        "initial": params.get("default"),
        "disabled": field_def.read_only,
    }
    field_type = field_def.type

    if field_type == "text":
        return forms.CharField(
            widget=UnfoldAdminTextareaWidget, **common
        )
    if field_type == "enum":
        return forms.ChoiceField(
            choices=field_def.options or [],
            widget=UnfoldAdminSelectWidget,
            **common,
        )
    if field_type == "multi_enum":
        return forms.MultipleChoiceField(
            choices=field_def.options or [],
            widget=UnfoldAdminCheckboxSelectMultipleWidget,
            **common,
        )
    if field_type == "bool":
        return forms.BooleanField(
            widget=UnfoldBooleanSwitchWidget, **{**common, "required": False}
        )
    if field_type == "int":
        return forms.IntegerField(widget=UnfoldAdminIntegerFieldWidget, **common)
    if field_type in {"float", "currency"}:
        return forms.DecimalField(
            max_digits=params.get("max_digits", 16),
            decimal_places=params.get("decimal_places", 2),
            widget=UnfoldAdminDecimalFieldWidget,
            **common,
        )
    if field_type == "date":
        return forms.DateField(widget=UnfoldAdminSingleDateWidget, **common)
    if field_type == "datetime":
        return forms.DateTimeField(widget=UnfoldAdminSplitDateTimeWidget, **common)
    if field_type == "email":
        return forms.EmailField(widget=UnfoldAdminEmailInputWidget, **common)
    if field_type == "url":
        return forms.URLField(widget=UnfoldAdminURLInputWidget, **common)
    return forms.CharField(
        max_length=params.get("max_length", 255),
        widget=UnfoldAdminTextInputWidget,
        **common,
    )


def form_field_name(field_def: FieldDef) -> str:
    """Name of the generated admin form field for a custom field."""

    return f"custom__{field_def.name}"


def custom_field_names(custom_fields) -> list[str]:
    return [form_field_name(field_def) for field_def in custom_fields]


def build_list_filter(field_def: FieldDef):
    """Create a SimpleListFilter class for an enum/bool custom field."""

    if field_def.type in {"enum", "multi_enum"} and field_def.options:
        class _ChoicesFilter(admin.SimpleListFilter):
            title = field_def.display_label
            parameter_name = f"cf_{field_def.name}"

            def lookups(self, request, model_admin):
                return list(field_def.options or [])

            def queryset(self, request, queryset):
                if self.value():
                    return queryset.filter(**{f"custom_data__{field_def.name}": self.value()})
                return queryset

        _ChoicesFilter.__name__ = f"CustomFilter_{slugify(field_def.name).replace('-', '_')}"
        return _ChoicesFilter

    if field_def.type == "bool":
        class _BoolFilter(admin.SimpleListFilter):
            title = field_def.display_label
            parameter_name = f"cf_{field_def.name}"

            def lookups(self, request, model_admin):
                return (("true", "Yes"), ("false", "No"))

            def queryset(self, request, queryset):
                if self.value() in {"true", "false"}:
                    return queryset.filter(
                        **{f"custom_data__{field_def.name}": self.value() == "true"}
                    )
                return queryset

        _BoolFilter.__name__ = f"CustomFilter_{slugify(field_def.name).replace('-', '_')}"
        return _BoolFilter

    return None


def display_custom_value(field_def: FieldDef, value):
    """Human-readable representation of a custom field value."""

    if value in (None, ""):
        return "-"
    if field_def.type == "bool":
        return "Yes" if value else "No"
    if field_def.type == "enum" and field_def.options:
        mapping = {str(key): label for key, label in field_def.options}
        return mapping.get(str(value), value)
    return value

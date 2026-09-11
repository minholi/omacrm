"""Mapping of metadata field types to Django forms, widgets and filters."""

from django import forms
from django.urls import reverse
from django.utils.text import slugify

from omacrm.core.metadata.defs import FieldDef
from unfold.widgets import (
    UnfoldAdminAutocompleteModelChoiceFieldWidget,
    UnfoldAdminCheckboxSelectMultipleWidget,
    UnfoldAdminDecimalFieldWidget,
    UnfoldAdminEmailInputWidget,
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminMultipleAutocompleteModelChoiceFieldWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminSingleDateWidget,
    UnfoldAdminSplitDateTimeWidget,
    UnfoldAdminTextInputWidget,
    UnfoldAdminTextareaWidget,
    UnfoldAdminURLInputWidget,
    UnfoldBooleanSwitchWidget,
)

SIMPLE_TEXT_TYPES = {"varchar", "enum"}

ADDRESS_KEYS = ("street", "city", "state", "postal_code", "country")
ADDRESS_LABELS = {
    "street": "Street",
    "city": "City",
    "state": "State",
    "postal_code": "Postal Code",
    "country": "Country",
}


class CustomAttachmentWidget(forms.Widget):
    """File input that also lists the files already stored on the record."""

    template_name = "admin/widgets/custom_attachment_input.html"

    def __init__(self, attrs=None, multiple=False, clearable=False):
        super().__init__(attrs)
        self.multiple = multiple
        self.clearable = clearable

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["multiple"] = self.multiple
        context["clearable"] = self.clearable
        context["current_files"] = (self.attrs or {}).get("current_files", [])
        return context

    def value_from_datadict(self, data, files, name):
        if self.multiple:
            return files.getlist(name)
        return files.get(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files and f"{name}-clear" not in data


class MultipleAttachmentField(forms.Field):
    """Accepts several uploaded files for an attachmentMultiple field."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", CustomAttachmentWidget(multiple=True))
        super().__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [upload for upload in value if upload]


class AddressWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [
            UnfoldAdminTextInputWidget(
                attrs={"placeholder": ADDRESS_LABELS[key]}
            )
            for key in ADDRESS_KEYS
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if isinstance(value, dict):
            return [value.get(key, "") for key in ADDRESS_KEYS]
        return ["" for _key in ADDRESS_KEYS]


class AddressField(forms.MultiValueField):
    def __init__(self, **kwargs):
        fields = [forms.CharField(required=False) for _key in ADDRESS_KEYS]
        kwargs.setdefault("require_all_fields", False)
        kwargs.setdefault("widget", AddressWidget)
        super().__init__(fields=fields, **kwargs)

    def compress(self, values):
        if not values:
            return None
        data = {
            key: value for key, value in zip(ADDRESS_KEYS, values) if value
        }
        return data or None


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
    if field_type == "decimal":
        return forms.DecimalField(
            max_digits=params.get("max_digits", 18),
            decimal_places=params.get("decimal_places", 6),
            widget=UnfoldAdminDecimalFieldWidget,
            **common,
        )
    if field_type == "number":
        return forms.CharField(
            widget=UnfoldAdminTextInputWidget,
            **{**common, "required": False, "disabled": True},
        )
    if field_type == "date":
        return forms.DateField(widget=UnfoldAdminSingleDateWidget, **common)
    if field_type == "datetime":
        return forms.DateTimeField(widget=UnfoldAdminSplitDateTimeWidget, **common)
    if field_type == "email":
        return forms.EmailField(widget=UnfoldAdminEmailInputWidget, **common)
    if field_type == "phone":
        return forms.CharField(
            max_length=50, widget=UnfoldAdminTextInputWidget, **common
        )
    if field_type == "url":
        return forms.URLField(widget=UnfoldAdminURLInputWidget, **common)
    if field_type == "address":
        return AddressField(**common)
    if field_type == "foreign":
        return forms.CharField(
            widget=UnfoldAdminTextInputWidget,
            **{**common, "required": False, "disabled": True, "initial": ""},
        )
    if field_type == "file":
        return forms.FileField(
            widget=CustomAttachmentWidget(clearable=True),
            **{**common, "initial": ""},
        )
    if field_type == "image":
        return forms.ImageField(
            widget=CustomAttachmentWidget(clearable=True),
            **{**common, "initial": ""},
        )
    if field_type == "attachmentMultiple":
        return MultipleAttachmentField(
            **{**common, "required": False, "initial": ""}
        )
    return forms.CharField(
        max_length=params.get("max_length", 255),
        widget=UnfoldAdminTextInputWidget,
        **common,
    )


def form_field_name(field_def: FieldDef) -> str:
    """Name of the generated admin form field for a custom field."""

    return f"custom__{field_def.name}"


def link_form_field_name(field_def: FieldDef) -> str:
    """Name of the generated admin form field for a custom link."""

    return f"link__{field_def.name}"


class LinkChoiceField(forms.ModelChoiceField):
    """Single link picker that only renders the currently linked records."""

    def __init__(self, *args, current=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.choices = [(obj.pk, str(obj)) for obj in current]


class LinkMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Multiple link picker that only renders the currently linked records."""

    def __init__(self, *args, current=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.choices = [(obj.pk, str(obj)) for obj in current]


def build_link_form_field(field_def: FieldDef, user=None) -> forms.Field:
    """Build an admin form field for a custom relationship."""

    from omacrm.core.metadata.registry import registry
    from omacrm.core.services.acl import AclService

    params = field_def.params or {}
    target_entity = params.get("target_entity", "")
    model = registry.model_for(target_entity)
    queryset = model.objects.all()
    if user is not None and getattr(user, "is_authenticated", False):
        queryset = AclService.scope_queryset(user, target_entity, queryset, "read")
    ordering = registry.get(target_entity).ordering or ["pk"]
    queryset = queryset.order_by(*ordering)

    ajax_url = f"{reverse('link_autocomplete')}?entity_type={target_entity}"
    if field_def.type == "link":
        widget = UnfoldAdminAutocompleteModelChoiceFieldWidget(
            attrs={"data-ajax--url": ajax_url}
        )
        return LinkChoiceField(
            queryset=queryset,
            widget=widget,
            required=False,
            label=field_def.display_label,
        )
    widget = UnfoldAdminMultipleAutocompleteModelChoiceFieldWidget(
        attrs={"data-ajax--url": ajax_url}
    )
    return LinkMultipleChoiceField(
        queryset=queryset,
        widget=widget,
        required=False,
        label=field_def.display_label,
    )


def custom_field_names(custom_fields) -> list[str]:
    return [form_field_name(field_def) for field_def in custom_fields]


def build_list_filter(field_def: FieldDef):
    """Create an Unfold dropdown filter for an enum/bool custom field."""

    from unfold.contrib.filters.admin import DropdownFilter

    if field_def.type in {"enum", "multi_enum"} and field_def.options:
        class _ChoicesFilter(DropdownFilter):
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
        class _BoolFilter(DropdownFilter):
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

import csv
import uuid
from urllib.parse import urlencode

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.utils import flatten_fieldsets
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.forms import BaseDialogForm
from unfold.widgets import UnfoldAdminTextareaWidget

from omacrm.core.admin.datasets import note_dataset_for
from omacrm.core.admin.inlines import AttachmentInline
from omacrm.core.metadata.fields import (
    build_form_field,
    build_list_filter,
    display_custom_value,
    form_field_name,
)
from omacrm.core.metadata.registry import registry
from omacrm.core.services.acl import AclService
from omacrm.core.services.duplicates import DuplicateConflict, check_duplicates
from omacrm.core.services.stream import post_note

AUDIT_READONLY = (
    "created_at",
    "modified_at",
    "created_by",
    "modified_by",
    "custom_data",
)


class NotePostForm(BaseDialogForm):
    post = forms.CharField(
        label=_("Message"),
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 4}),
    )
    is_internal = forms.BooleanField(label=_("Internal note"), required=False)


class AclAdminMixin:
    """Wires role/team/ownership ACL into a Django ModelAdmin."""

    entity_type = ""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def _acl_check(self, request, action, obj=None):
        if not self.entity_type:
            return super().has_view_permission(request, obj)
        return AclService.check(request.user, self.entity_type, action, obj)

    def has_view_permission(self, request, obj=None):
        if not self.entity_type:
            return super().has_view_permission(request, obj)
        return self._acl_check(request, "read", obj)

    def has_add_permission(self, request):
        if not self.entity_type:
            return super().has_add_permission(request)
        return self._acl_check(request, "create")

    def has_change_permission(self, request, obj=None):
        if not self.entity_type:
            return super().has_change_permission(request, obj)
        return self._acl_check(request, "edit", obj)

    def has_delete_permission(self, request, obj=None):
        if not self.entity_type:
            return super().has_delete_permission(request, obj)
        return self._acl_check(request, "delete", obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not self.entity_type or request.user.is_superuser:
            return queryset
        return AclService.scope_queryset(request.user, self.entity_type, queryset, "read")


class MetadataModelAdmin(AclAdminMixin, SimpleHistoryAdmin, ModelAdmin):
    """ModelAdmin driven by the metadata registry.

    Renders layouts, merges custom fields into forms/lists/filters and
    enforces ACL. Business entities should set ``entity_type``.
    """

    actions = ("export_as_csv", "mass_update")
    actions_detail = ("add_note",)

    change_list_template = "admin/saved_filters_change_list.html"

    # -- saved filters ------------------------------------------------------

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        entity_type = self.entity_type
        user = request.user

        if entity_type and user.is_authenticated:
            from omacrm.core.models import SavedFilter

            reserved = {"save_filter", "apply_filter", "delete_filter"}

            name = request.GET.get("save_filter")
            if name and name.strip():
                params = {
                    key: values if len(values) > 1 else values[0]
                    for key, values in request.GET.lists()
                    if key not in reserved
                }
                SavedFilter.objects.update_or_create(
                    user=user,
                    entity_type=entity_type,
                    name=name.strip()[:100],
                    defaults={"params": params},
                )
                self.message_user(request, _("Filter saved."), level=messages.SUCCESS)
                query = urlencode(params, doseq=True)
                return redirect(f"{request.path}?{query}" if query else request.path)

            apply_id = request.GET.get("apply_filter")
            if apply_id:
                saved = SavedFilter.objects.filter(
                    pk=apply_id, user=user, entity_type=entity_type
                ).first()
                if saved:
                    query = urlencode(saved.params, doseq=True)
                    return redirect(f"{request.path}?{query}" if query else request.path)
                return redirect(request.path)

            delete_id = request.GET.get("delete_filter")
            if delete_id:
                SavedFilter.objects.filter(
                    pk=delete_id, user=user, entity_type=entity_type
                ).delete()
                self.message_user(
                    request, _("Filter removed."), level=messages.SUCCESS
                )
                return redirect(request.path)

            extra_context["saved_filters"] = SavedFilter.objects.filter(
                user=user, entity_type=entity_type
            ).order_by("name")

        return super().changelist_view(request, extra_context=extra_context)

    # -- stream / attachments ----------------------------------------------

    def get_actions_detail(self, request, object_id):
        actions = list(super().get_actions_detail(request, object_id))
        if not self.entity_type or not self.metadata_entity().stream:
            actions = [
                item
                for item in actions
                if getattr(item.method, "original_function_name", "") != "add_note"
            ]
        return actions

    def get_changeform_datasets(self, request):
        datasets = list(super().get_changeform_datasets(request))
        if self.entity_type and self.metadata_entity().stream:
            datasets.append(note_dataset_for(self.model))
        return datasets

    def get_inlines(self, request, obj=None):
        inlines = list(super().get_inlines(request, obj))
        if self.entity_type and self.metadata_entity().stream:
            inlines.append(AttachmentInline)
        return inlines

    @action(
        description=_("Post Note"),
        icon="forum",
        dialog={
            "title": _("Post Note"),
            "description": _("Add a note to the record stream."),
            "form_class": NotePostForm,
            "form_submit_text": _("Post"),
        },
    )
    def add_note(self, request, form, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            messages.error(request, _("Record not found."))
            return HttpResponse(
                headers={
                    "HX-Redirect": reverse(
                        f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
                    )
                }
            )
        if not self.has_change_permission(request, obj):
            messages.error(request, _("You do not have permission to post notes."))
        else:
            post_note(
                obj,
                form.cleaned_data["post"],
                user=request.user,
                is_internal=form.cleaned_data.get("is_internal", False),
            )
            messages.success(request, _("Note posted."))
        return HttpResponse(
            headers={
                "HX-Redirect": reverse(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                    args=[obj.pk],
                )
            }
        )

    # -- metadata helpers ---------------------------------------------------

    def metadata_entity(self):
        return registry.get(self.entity_type)

    def get_metadata_fields(self):
        return registry.fields(self.entity_type)

    # -- permissions --------------------------------------------------------

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        for name in AUDIT_READONLY:
            if name not in readonly:
                readonly.append(name)
        for name, field_def in self.get_metadata_fields().items():
            if field_def.read_only and name not in readonly:
                readonly.append(name)
        for name in sorted(AclService.forbidden_fields(request.user, self.entity_type)):
            if name not in readonly:
                readonly.append(name)

        valid_fields = {field.name for field in self.model._meta.get_fields()}
        return [
            name
            for name in readonly
            if name in valid_fields or hasattr(self, name)
        ]

    # -- layout-driven rendering -------------------------------------------

    def get_fieldsets(self, request, obj=None):
        custom_names = [
            form_field_name(field_def)
            for field_def in registry.custom_fields(self.entity_type)
        ]
        layout = registry.layout(self.entity_type, "detail")
        if layout:
            fieldsets = [
                (section.get("title") or None, {"fields": list(section.get("fields", [])), **{k: v for k, v in section.items() if k in {"classes", "description"}}})
                for section in layout
            ]
        else:
            fieldsets = list(super().get_fieldsets(request, obj))
        if custom_names:
            fieldsets.append((_("Custom Fields"), {"fields": custom_names}))
        return fieldsets

    def _custom_display(self, field_def):
        def display(obj):
            return display_custom_value(
                field_def, (obj.custom_data or {}).get(field_def.name)
            )

        display.short_description = field_def.display_label
        display.admin_order_field = f"custom_data__{field_def.name}"
        return display

    def get_list_display(self, request):
        base = list(super().get_list_display(request))
        entity = self.metadata_entity()
        if entity.list_layout and tuple(base) == ("__str__",):
            base = list(entity.list_layout)
        for field_def in registry.custom_fields(self.entity_type):
            base.append(self._custom_display(field_def))
        return base

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        if not filters:
            filters = list(self.metadata_entity().list_filter)
        for field_def in registry.custom_fields(self.entity_type):
            filter_class = build_list_filter(field_def)
            if filter_class is not None:
                filters.append(filter_class)
        return filters

    def get_search_fields(self, request):
        fields = list(super().get_search_fields(request))
        if not fields:
            fields = list(self.metadata_entity().search_fields)
        for field_def in registry.custom_fields(self.entity_type):
            if field_def.type in {"varchar", "text", "email"}:
                fields.append(f"custom_data__{field_def.name}")
        return fields

    # -- dynamic form (custom fields + duplicate checks) --------------------

    def get_form(self, request, obj=None, change=False, **kwargs):
        custom_fields = registry.custom_fields(self.entity_type)
        custom_names = {form_field_name(field_def) for field_def in custom_fields}
        if custom_names:
            kwargs["fields"] = [
                name
                for name in flatten_fieldsets(self.get_fieldsets(request, obj))
                if name not in custom_names
            ]
        base_form = super().get_form(request, obj, change=change, **kwargs)
        entity = self.metadata_entity()
        entity_type = self.entity_type

        class _MetadataForm(base_form):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                instance = getattr(self, "instance", None)
                for field_def in custom_fields:
                    name = form_field_name(field_def)
                    if name in self.fields and instance is not None and instance.pk:
                        self.fields[name].initial = (instance.custom_data or {}).get(
                            field_def.name
                        )

            def clean(self):
                cleaned = super().clean()
                data = dict(getattr(self.instance, "custom_data", {}) or {})
                for field_def in custom_fields:
                    name = form_field_name(field_def)
                    if name in cleaned and cleaned[name] not in (None, ""):
                        data[field_def.name] = cleaned[name]
                    else:
                        data.pop(field_def.name, None)
                self._custom_data = data
                return cleaned

            def _post_clean(self):
                super()._post_clean()
                if entity.duplicate_check_fields:
                    try:
                        check_duplicates(entity_type, self.instance)
                    except DuplicateConflict as exc:
                        self.add_error(None, str(exc))

        for field_def in custom_fields:
            _MetadataForm = type(
                base_form.__name__,
                (_MetadataForm,),
                {form_field_name(field_def): build_form_field(field_def)},
            )
        return _MetadataForm

    # -- persistence --------------------------------------------------------

    def save_model(self, request, obj, form, change):
        custom_data = getattr(form, "_custom_data", None)
        if custom_data is not None:
            obj.custom_data = custom_data
        if not change and hasattr(obj, "created_by_id"):
            obj.created_by = request.user
        if hasattr(obj, "modified_by_id"):
            obj.modified_by = request.user
        super().save_model(request, obj, form, change)

    # -- mass update --------------------------------------------------------

    def mass_update_url_name(self):
        meta = self.model._meta
        return f"{meta.app_label}_{meta.model_name}_mass_update"

    def get_custom_urls(self):
        from omacrm.core.admin.views import MassUpdateView

        return tuple(super().get_custom_urls()) + (
            ("mass-update/", self.mass_update_url_name(), MassUpdateView.as_view()),
        )

    def mass_update_fields(self) -> list[dict]:
        """Editable fields offered by the mass update form."""

        from django.contrib.auth import get_user_model

        entity = self.metadata_entity()
        model_fields = {field.name for field in self.model._meta.get_fields()}
        fields = []

        for name, field_def in registry.fields(self.entity_type).items():
            if field_def.custom or field_def.read_only or name not in model_fields:
                continue
            if field_def.type == "enum" and field_def.options:
                fields.append(
                    {
                        "name": name,
                        "label": field_def.display_label,
                        "choices": list(field_def.options),
                    }
                )
            elif field_def.type == "bool":
                fields.append(
                    {
                        "name": name,
                        "label": field_def.display_label,
                        "choices": [("True", _("Yes")), ("False", _("No"))],
                    }
                )

        if "assigned_user" in model_fields:
            users = get_user_model().objects.filter(is_active=True).order_by("user_name")
            fields.append(
                {
                    "name": "assigned_user",
                    "label": _("Assigned User"),
                    "choices": [("", _("Unassigned"))]
                    + [(str(user.pk), user.name) for user in users],
                }
            )

        return fields

    @admin.action(description=_("Mass update selected records"))
    def mass_update(self, request, queryset):
        if not self.has_change_permission(request) or not self.mass_update_fields():
            self.message_user(
                request, _("Mass update is not available."), level=messages.WARNING
            )
            return None

        token = uuid.uuid4().hex
        request.session[f"mass_update:{token}"] = {
            "pks": list(queryset.values_list("pk", flat=True))
        }
        url = reverse(f"admin:{self.mass_update_url_name()}")
        return redirect(f"{url}?token={token}")

    # -- actions ------------------------------------------------------------

    @admin.action(description=_("Export selected records as CSV"))
    def export_as_csv(self, request, queryset):
        fields = [
            name
            for name, field_def in self.get_metadata_fields().items()
            if not field_def.custom
            and name not in {"custom_data"}
        ]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{self.entity_type or "records"}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(fields)
        for obj in queryset:
            writer.writerow([getattr(obj, name, "") for name in fields])
        return response

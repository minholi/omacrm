"""Form widgets for the admin authoring editors.

The widgets render a normal textarea (so the form keeps working without
JavaScript) plus a JSON config block consumed by
``core/static/core/js/editors.js`` for completion and live validation.
"""

from django.urls import reverse
from unfold.widgets import UnfoldAdminTextareaWidget


class EditorWidget(UnfoldAdminTextareaWidget):
    """Base widget for a CodeMirror-enhanced textarea."""

    template_name = "admin/widgets/editor_field.html"
    mode = "json"

    def __init__(
        self,
        attrs=None,
        kind="",
        entity_field="",
        fixed_entity="",
        context_fields=(),
        rows=10,
    ):
        attrs = {"rows": rows, **(attrs or {})}
        super().__init__(attrs)
        self.kind = kind
        self.entity_field = entity_field
        self.fixed_entity = fixed_entity
        self.context_fields = tuple(context_fields)

    class Media:
        js = (
            "vendor/codemirror/codemirror6.bundle.js",
            "core/js/editors.js",
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_id = context["widget"]["attrs"]["id"]
        context["config_id"] = f"{widget_id}-config"
        context["editor"] = {
            "mode": self.mode,
            "kind": self.kind,
            "entityField": self.entity_field,
            "fixedEntity": self.fixed_entity,
            "contextFields": list(self.context_fields),
            "metadataUrl": reverse(
                "editor_metadata", kwargs={"entity_type": "__entity__"}
            ),
            "validateUrl": reverse("editor_validate"),
        }
        return context


class JSONEditorWidget(EditorWidget):
    mode = "json"


class ScriptEditorWidget(EditorWidget):
    mode = "script"

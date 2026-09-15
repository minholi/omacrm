"""Form widgets for the admin authoring editors.

The widgets render a normal textarea (so the form keeps working without
JavaScript) plus a JSON config block consumed by
``core/static/core/js/editors.js`` for completion and live validation.
"""

from django.urls import reverse
from unfold.widgets import INPUT_CLASSES, SELECT_CLASSES, TEXTAREA_CLASSES
from unfold.widgets import UnfoldAdminTextareaWidget

_BUTTON_BASE = (
    "font-medium inline-flex group items-center gap-1 relative rounded-default "
    "justify-center whitespace-nowrap cursor-pointer px-2.5 py-1.5 "
)

EDITOR_CLASSES = {
    "input": " ".join(INPUT_CLASSES),
    "select": " ".join(SELECT_CLASSES),
    "textarea": " ".join(TEXTAREA_CLASSES),
    "button": _BUTTON_BASE
    + "border border-base-200 bg-white shadow-xs "
    + "text-font-important-light dark:border-base-700 dark:bg-transparent "
    + "dark:text-font-important-dark hover:bg-base-100/80 "
    + "dark:hover:bg-base-800/80",
    "primary": _BUTTON_BASE
    + "border border-transparent bg-primary-600 text-white "
    + "hover:bg-primary-600/80",
    "subtle": "text-xs text-font-subtle-light dark:text-font-subtle-dark",
    "important": (
        "font-semibold text-sm text-font-important-light "
        "dark:text-font-important-dark"
    ),
}


class EditorWidget(UnfoldAdminTextareaWidget):
    """Base widget for a CodeMirror-enhanced textarea."""

    template_name = "admin/widgets/editor_field.html"
    mode = "json"
    visual_kinds = (
        "workflow_actions",
        "dynamic_logic",
        "custom_field",
        "lead_capture",
        "layout",
        "reminders",
        "recurrence",
    )

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
            "core/js/builders.js",
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
            "tabs": self.mode == "json" and self.kind in self.visual_kinds,
            "classes": EDITOR_CLASSES,
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

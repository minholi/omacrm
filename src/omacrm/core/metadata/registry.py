import importlib

from django.db import ProgrammingError, OperationalError

from omacrm.core.metadata.defs import EntityDef, FieldDef

DYNAMIC_BASE_FIELDS = {
    "name": FieldDef(
        "name", "varchar", "Name", required=True, model_field="name"
    ),
    "assigned_user": FieldDef(
        "assigned_user", "link", "Assigned User", model_field="assigned_user"
    ),
    "teams": FieldDef(
        "teams", "linkMultiple", "Teams", model_field="teams"
    ),
    "created_at": FieldDef(
        "created_at", "datetime", "Created At", read_only=True, model_field="created_at"
    ),
    "modified_at": FieldDef(
        "modified_at", "datetime", "Modified At", read_only=True, model_field="modified_at"
    ),
}


class MetadataRegistry:
    """Merges built-in entity definitions with DB-stored customizations.

    Built-in definitions register themselves from each app's ``metadata``
    module (autodiscovered on first access). Custom fields, layouts and
    runtime-defined custom entities are stored in the database and layered on
    top.
    """

    def __init__(self):
        self._entities: dict[str, EntityDef] = {}
        self._loaded = False
        self._custom_fields: dict[str, list[FieldDef]] = {}
        self._custom_entity_cache: list[str] | None = None

    # -- registration -------------------------------------------------------

    def register(self, entity: EntityDef) -> EntityDef:
        self._entities[entity.entity_type] = entity
        return entity

    def unregister(self, entity_type: str) -> None:
        self._entities.pop(entity_type, None)
        self._custom_fields.pop(entity_type, None)
        self._custom_entity_cache = None

    def autodiscover(self) -> None:
        if self._loaded:
            return
        from django.apps import apps

        for config in apps.get_app_configs():
            module_name = f"{config.name}.metadata"
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                if exc.name != module_name:
                    raise
        self._loaded = True

    def invalidate(self) -> None:
        self._custom_fields.clear()
        self._custom_entity_cache = None
        self._loaded = False

    # -- custom entities ----------------------------------------------------

    def custom_entity_names(self) -> list[str]:
        if self._custom_entity_cache is not None:
            return self._custom_entity_cache

        from omacrm.core.models import CustomEntity

        try:
            names = list(
                CustomEntity.objects.filter(is_active=True)
                .order_by("name")
                .values_list("name", flat=True)
            )
        except (OperationalError, ProgrammingError):
            names = []
        self._custom_entity_cache = names
        return names

    def is_builtin(self, entity_type: str) -> bool:
        self.autodiscover()
        return entity_type in self._entities

    def is_dynamic(self, entity_type: str) -> bool:
        return entity_type in self.custom_entity_names()

    def _dynamic_entity_def(self, entity_type: str) -> EntityDef:
        from omacrm.core.models import CustomEntity

        row = None
        if entity_type:
            try:
                row = CustomEntity.objects.filter(
                    name=entity_type, is_active=True
                ).first()
            except (OperationalError, ProgrammingError):
                row = None
        label = row.display_label if row else entity_type
        label_plural = row.display_label_plural if row else f"{entity_type}s"

        fields = dict(DYNAMIC_BASE_FIELDS)
        detail_layout = [
            {"title": "Overview", "fields": ["name"]},
            {
                "title": "Assignment",
                "fields": ["assigned_user", "teams", "created_at", "modified_at"],
            },
        ]
        return EntityDef(
            entity_type=entity_type,
            model=f"core.{entity_type}",
            label=label,
            label_plural=label_plural,
            fields=fields,
            ordering=list(row.ordering) if row else ["-created_at"],
            search_fields=list(row.search_field_list) if row else ["name"],
            list_layout=["name"],
            list_filter=["assigned_user"],
            detail_layout=detail_layout,
            stream=row.stream if row else True,
            calendar=row.show_in_calendar if row else False,
            kanban_field=(row.status_field if row else "") or "",
            duplicate_check_fields=(
                list(row.duplicate_field_list) if row else []
            ),
            icon=(row.icon if row else "") or "extension",
            dynamic=True,
        )

    # -- access -------------------------------------------------------------

    def entities(self) -> dict[str, EntityDef]:
        self.autodiscover()
        result = dict(self._entities)
        for name in self.custom_entity_names():
            result.setdefault(name, self._dynamic_entity_def(name))
        return result

    def entity_types(self) -> list[str]:
        return sorted(self.entities().keys())

    def get(self, entity_type: str) -> EntityDef:
        self.autodiscover()
        if entity_type in self._entities:
            return self._entities[entity_type]
        if self.is_dynamic(entity_type):
            return self._dynamic_entity_def(entity_type)
        raise KeyError(f"Unknown entity type: {entity_type}")

    def has(self, entity_type: str) -> bool:
        return entity_type in self.entities()

    def fields(self, entity_type: str) -> dict[str, FieldDef]:
        entity = self.get(entity_type)
        fields = dict(entity.fields)
        if entity.dynamic:
            fields.update(DYNAMIC_BASE_FIELDS)
        for custom in self.custom_fields(entity_type):
            fields[custom.name] = custom
        return fields

    def field(self, entity_type: str, name: str) -> FieldDef | None:
        return self.fields(entity_type).get(name)

    # -- custom links -------------------------------------------------------

    def link_definitions(self, entity_type: str):
        from omacrm.core.metadata.links import link_definitions

        return link_definitions(entity_type)

    def link_fields(self, entity_type: str) -> dict[str, FieldDef]:
        result: dict[str, FieldDef] = {}
        for name, definition in self.link_definitions(entity_type).items():
            result[name] = FieldDef(
                name=name,
                type=definition.field_type,
                label=definition.label,
                custom=True,
                params={
                    "link_name": definition.name,
                    "target_entity": definition.target_entity,
                    "link_type": definition.link_type,
                    "custom_link": True,
                },
            )
        return result

    def custom_fields(self, entity_type: str) -> list[FieldDef]:
        if entity_type in self._custom_fields:
            return self._custom_fields[entity_type]

        from omacrm.core.models import CustomField

        try:
            rows = list(
                CustomField.objects.filter(entity_type=entity_type, is_active=True)
            )
        except (OperationalError, ProgrammingError):
            rows = []

        result = [
            FieldDef(
                name=row.name,
                type=row.field_type,
                label=row.display_label,
                required=row.required,
                read_only=row.read_only,
                order=row.order,
                params=dict(row.params or {}),
                custom=True,
                options=row.params.get("choices") if row.params else None,
            )
            for row in rows
        ]
        self._custom_fields[entity_type] = result
        return result

    def entity_type_for_instance(self, instance) -> str | None:
        self.autodiscover()

        from omacrm.core.models import DynamicRecord

        if isinstance(instance, DynamicRecord):
            return getattr(instance, "entity_type", None)

        label = instance._meta.label
        for entity_type, entity in self._entities.items():
            if entity.model == label:
                return entity_type
        return None

    def model_for(self, entity_type: str):
        from django.apps import apps as django_apps

        model = self.get(entity_type).model
        try:
            return django_apps.get_model(model)
        except LookupError:
            return django_apps.get_model("core", "DynamicRecord")

    def layout(self, entity_type: str, layout_name: str) -> dict | list | None:
        from omacrm.core.models import Layout

        try:
            row = Layout.objects.filter(
                entity_type=entity_type, layout_name=layout_name
            ).first()
        except (OperationalError, ProgrammingError):
            row = None
        if row is not None:
            return row.data

        entity = self.get(entity_type)
        if layout_name in {"detail", "edit"}:
            return entity.detail_layout or None
        if layout_name == "list":
            return entity.list_layout or None
        return None


registry = MetadataRegistry()

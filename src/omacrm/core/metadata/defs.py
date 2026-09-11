from dataclasses import dataclass, field as dataclass_field


@dataclass
class FieldDef:
    """Declarative description of an entity attribute (built-in or custom)."""

    name: str
    type: str = "varchar"
    label: str = ""
    required: bool = False
    read_only: bool = False
    options: list | None = None
    help_text: str = ""
    model_field: str | None = None
    custom: bool = False
    order: int = 100
    params: dict = dataclass_field(default_factory=dict)

    @property
    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()


@dataclass
class EntityDef:
    """Declarative description of a record type."""

    entity_type: str
    model: str
    label: str = ""
    label_plural: str = ""
    fields: dict = dataclass_field(default_factory=dict)
    ordering: list = dataclass_field(default_factory=list)
    search_fields: list = dataclass_field(default_factory=list)
    list_display: list = dataclass_field(default_factory=list)
    list_filter: list = dataclass_field(default_factory=list)
    detail_layout: list = dataclass_field(default_factory=list)
    list_layout: list = dataclass_field(default_factory=list)
    stream: bool = False
    calendar: bool = False
    duplicate_check_fields: list = dataclass_field(default_factory=list)
    icon: str = "table"
    acl_default: str = "all"
    dynamic: bool = False

    @property
    def display_label(self) -> str:
        return self.label or self.entity_type

    @property
    def display_label_plural(self) -> str:
        return self.label_plural or f"{self.display_label}s"

    def field(self, name: str) -> FieldDef | None:
        return self.fields.get(name)

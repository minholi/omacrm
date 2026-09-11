from django.utils.translation import gettext_lazy as _

from omacrm.core.metadata.defs import EntityDef, FieldDef
from omacrm.core.metadata.registry import registry
from omacrm.core.models import User

USER_FIELDS = {
    "user_name": FieldDef("user_name", "varchar", _("User Name"), required=True, model_field="user_name"),
    "first_name": FieldDef("first_name", "varchar", _("First Name"), model_field="first_name"),
    "last_name": FieldDef("last_name", "varchar", _("Last Name"), model_field="last_name"),
    "email": FieldDef("email", "email", _("Email"), model_field="email"),
    "type": FieldDef(
        "type",
        "enum",
        _("Type"),
        model_field="type",
        options=list(User.Type.choices),
    ),
    "is_active": FieldDef("is_active", "bool", _("Active"), model_field="is_active"),
    "is_staff": FieldDef("is_staff", "bool", _("Staff"), model_field="is_staff"),
    "title": FieldDef("title", "varchar", _("Title"), model_field="title"),
    "phone_number": FieldDef("phone_number", "varchar", _("Phone"), model_field="phone_number"),
    "default_team": FieldDef("default_team", "link", _("Default Team"), model_field="default_team"),
    "teams": FieldDef("teams", "linkMultiple", _("Teams"), model_field="teams"),
    "roles": FieldDef("roles", "linkMultiple", _("Roles"), model_field="roles"),
    "last_access": FieldDef("last_access", "datetime", _("Last Access"), read_only=True, model_field="last_access"),
}

registry.register(
    EntityDef(
        entity_type="User",
        model="core.User",
        label=_("User"),
        label_plural=_("Users"),
        fields=USER_FIELDS,
        ordering=["user_name"],
        search_fields=["user_name", "first_name", "last_name", "email"],
        list_display=["user_name", "name", "email", "type", "is_active", "last_access"],
        list_filter=["type", "is_active", "is_staff"],
        list_layout=["user_name", "email", "type", "is_active", "last_access"],
        detail_layout=[
            {"title": _("Profile"), "fields": ["user_name", "first_name", "last_name", "email", "title", "phone_number"]},
            {"title": _("Access"), "fields": ["type", "is_active", "is_staff", "default_team", "teams", "roles", "api_key", "last_access"]},
            {"title": _("System"), "fields": ["created_at", "modified_at"]},
        ],
        icon="person",
        acl_default="no",
    )
)

registry.register(
    EntityDef(
        entity_type="Team",
        model="core.Team",
        label=_("Team"),
        label_plural=_("Teams"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "roles": FieldDef("roles", "linkMultiple", _("Roles"), model_field="roles"),
            "created_at": FieldDef("created_at", "datetime", _("Created At"), read_only=True, model_field="created_at"),
        },
        ordering=["name"],
        search_fields=["name", "description"],
        list_display=["name", "description", "created_at"],
        list_filter=["roles"],
        list_layout=["name", "description"],
        detail_layout=[
            {"title": None, "fields": ["name", "description", "roles", "created_at"]},
        ],
        icon="groups",
        acl_default="no",
    )
)

registry.register(
    EntityDef(
        entity_type="Role",
        model="core.Role",
        label=_("Role"),
        label_plural=_("Roles"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "data": FieldDef("data", "json", _("Scope Access Data"), read_only=True, model_field="data"),
            "field_data": FieldDef("field_data", "json", _("Field Access Data"), read_only=True, model_field="field_data"),
            "created_at": FieldDef("created_at", "datetime", _("Created At"), read_only=True, model_field="created_at"),
        },
        ordering=["name"],
        search_fields=["name", "description"],
        list_display=["name", "description", "created_at"],
        list_layout=["name", "description"],
        detail_layout=[
            {"title": None, "fields": ["name", "description", "data", "field_data", "created_at"]},
        ],
        icon="shield_person",
        acl_default="no",
    )
)

registry.register(
    EntityDef(
        entity_type="Preferences",
        model="core.Preferences",
        label=_("Preferences"),
        label_plural=_("Preferences"),
        fields={
            "user": FieldDef("user", "link", _("User"), required=True, model_field="user"),
            "time_zone": FieldDef("time_zone", "varchar", _("Time Zone"), model_field="time_zone"),
            "date_format": FieldDef("date_format", "varchar", _("Date Format"), model_field="date_format"),
            "time_format": FieldDef("time_format", "varchar", _("Time Format"), model_field="time_format"),
            "language": FieldDef("language", "varchar", _("Language"), model_field="language"),
            "default_currency": FieldDef("default_currency", "varchar", _("Default Currency"), model_field="default_currency"),
        },
        search_fields=["user__user_name"],
        list_display=["user", "language", "time_zone", "default_currency"],
        list_layout=["user", "language", "time_zone", "default_currency"],
        detail_layout=[
            {"title": None, "fields": ["user", "time_zone", "date_format", "time_format", "language", "default_currency"]},
        ],
        icon="tune",
        acl_default="no",
    )
)

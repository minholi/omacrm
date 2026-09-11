from django.utils.translation import gettext_lazy as _

from omacrm.core.metadata.defs import EntityDef, FieldDef
from omacrm.core.metadata.registry import registry
from omacrm.core.models import Email

registry.register(
    EntityDef(
        entity_type="Email",
        model="core.Email",
        label=_("Email"),
        label_plural=_("Emails"),
        fields={
            "subject": FieldDef("subject", "varchar", _("Subject"), model_field="subject"),
            "from_address": FieldDef("from_address", "email", _("From"), model_field="from_address"),
            "to_address": FieldDef("to_address", "text", _("To"), model_field="to_address"),
            "cc_address": FieldDef("cc_address", "text", _("Cc"), read_only=True, model_field="cc_address"),
            "bcc_address": FieldDef("bcc_address", "text", _("Bcc"), read_only=True, model_field="bcc_address"),
            "date_sent": FieldDef("date_sent", "datetime", _("Sent At"), read_only=True, model_field="date_sent"),
            "status": FieldDef("status", "enum", _("Status"), options=list(Email.Status.choices), read_only=True, model_field="status"),
            "is_read": FieldDef("is_read", "bool", _("Read"), model_field="is_read"),
            "message_id": FieldDef("message_id", "varchar", _("Message ID"), read_only=True, model_field="message_id"),
            "body": FieldDef("body", "text", _("Body"), model_field="body"),
            "body_plain": FieldDef("body_plain", "text", _("Body (plain)"), read_only=True, model_field="body_plain"),
            "assigned_user": FieldDef("assigned_user", "link", _("Assigned User"), model_field="assigned_user"),
            "created_at": FieldDef("created_at", "datetime", _("Created At"), read_only=True, model_field="created_at"),
            "modified_at": FieldDef("modified_at", "datetime", _("Modified At"), read_only=True, model_field="modified_at"),
        },
        ordering=["-date_sent", "-created_at"],
        search_fields=["subject", "from_address", "to_address", "body_plain"],
        list_layout=["subject", "from_address", "date_sent", "status", "is_read", "assigned_user"],
        list_filter=["status", "is_read", "assigned_user"],
        detail_layout=[
            {"title": _("Message"), "fields": ["subject", "from_address", "to_address", "cc_address", "date_sent", "is_read", "status", "assigned_user"]},
            {"title": _("Body"), "fields": ["body", "body_plain"]},
            {"title": _("System"), "fields": ["message_id", "created_at", "modified_at"]},
        ],
        stream=False,
        icon="mail",
    )
)

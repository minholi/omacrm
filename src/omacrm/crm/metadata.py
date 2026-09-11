from django.utils.translation import gettext_lazy as _

from omacrm.core.metadata.defs import EntityDef, FieldDef
from omacrm.core.metadata.registry import registry
from omacrm.crm.models import (
    AccountType,
    CallDirection,
    Campaign,
    Case,
    ContactRole,
    Document,
    EventStatus,
    Industry,
    KnowledgeBaseArticle,
    Lead,
    LeadSource,
    MassEmail,
    OpportunityStage,
    Salutation,
    TargetList,
    TaskPriority,
    TaskStatus,
)

AUDIT_FIELDS = {
    "assigned_user": FieldDef("assigned_user", "link", _("Assigned User"), model_field="assigned_user"),
    "teams": FieldDef("teams", "linkMultiple", _("Teams"), model_field="teams"),
    "created_at": FieldDef("created_at", "datetime", _("Created At"), read_only=True, model_field="created_at"),
    "modified_at": FieldDef("modified_at", "datetime", _("Modified At"), read_only=True, model_field="modified_at"),
}

ADDRESS_FIELDS = {
    "address_street": FieldDef("address_street", "varchar", _("Street"), model_field="address_street"),
    "address_city": FieldDef("address_city", "varchar", _("City"), model_field="address_city"),
    "address_state": FieldDef("address_state", "varchar", _("State"), model_field="address_state"),
    "address_country": FieldDef("address_country", "varchar", _("Country"), model_field="address_country"),
    "address_postal_code": FieldDef("address_postal_code", "varchar", _("Postal Code"), model_field="address_postal_code"),
}

registry.register(
    EntityDef(
        entity_type="Account",
        model="crm.Account",
        label=_("Account"),
        label_plural=_("Accounts"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "website": FieldDef("website", "url", _("Website"), model_field="website"),
            "email_address": FieldDef("email_address", "email", _("Email"), model_field="email_address"),
            "phone_number": FieldDef("phone_number", "varchar", _("Phone"), model_field="phone_number"),
            "type": FieldDef("type", "enum", _("Type"), options=list(AccountType.choices), model_field="type"),
            "industry": FieldDef("industry", "enum", _("Industry"), options=list(Industry.choices), model_field="industry"),
            "sic_code": FieldDef("sic_code", "varchar", _("SIC Code"), model_field="sic_code"),
            "billing_address_street": FieldDef("billing_address_street", "varchar", _("Billing Street"), model_field="billing_address_street"),
            "billing_address_city": FieldDef("billing_address_city", "varchar", _("Billing City"), model_field="billing_address_city"),
            "billing_address_state": FieldDef("billing_address_state", "varchar", _("Billing State"), model_field="billing_address_state"),
            "billing_address_country": FieldDef("billing_address_country", "varchar", _("Billing Country"), model_field="billing_address_country"),
            "billing_address_postal_code": FieldDef("billing_address_postal_code", "varchar", _("Billing Postal Code"), model_field="billing_address_postal_code"),
            "shipping_address_street": FieldDef("shipping_address_street", "varchar", _("Shipping Street"), model_field="shipping_address_street"),
            "shipping_address_city": FieldDef("shipping_address_city", "varchar", _("Shipping City"), model_field="shipping_address_city"),
            "shipping_address_state": FieldDef("shipping_address_state", "varchar", _("Shipping State"), model_field="shipping_address_state"),
            "shipping_address_country": FieldDef("shipping_address_country", "varchar", _("Shipping Country"), model_field="shipping_address_country"),
            "shipping_address_postal_code": FieldDef("shipping_address_postal_code", "varchar", _("Shipping Postal Code"), model_field="shipping_address_postal_code"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "is_locked": FieldDef("is_locked", "bool", _("Locked"), model_field="is_locked"),
            **AUDIT_FIELDS,
        },
        ordering=["name"],
        search_fields=["name", "email_address", "phone_number", "website"],
        list_layout=["name", "type", "industry", "phone_number", "assigned_user"],
        list_filter=["type", "industry", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "type", "industry", "email_address", "phone_number", "website", "sic_code", "description", "is_locked"]},
            {"title": _("Billing Address"), "fields": ["billing_address_street", "billing_address_city", "billing_address_state", "billing_address_country", "billing_address_postal_code"]},
            {"title": _("Shipping Address"), "fields": ["shipping_address_street", "shipping_address_city", "shipping_address_state", "shipping_address_country", "shipping_address_postal_code"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name", "email_address"],
        icon="domain",
    )
)

registry.register(
    EntityDef(
        entity_type="Contact",
        model="crm.Contact",
        label=_("Contact"),
        label_plural=_("Contacts"),
        fields={
            "salutation": FieldDef("salutation", "enum", _("Salutation"), options=list(Salutation.choices), model_field="salutation"),
            "first_name": FieldDef("first_name", "varchar", _("First Name"), model_field="first_name"),
            "last_name": FieldDef("last_name", "varchar", _("Last Name"), model_field="last_name"),
            "name": FieldDef("name", "varchar", _("Name"), model_field="name"),
            "title": FieldDef("title", "varchar", _("Title"), model_field="title"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "portal_user": FieldDef("portal_user", "link", _("Portal User"), model_field="portal_user"),
            "email_address": FieldDef("email_address", "email", _("Email"), model_field="email_address"),
            "phone_number": FieldDef("phone_number", "varchar", _("Phone"), model_field="phone_number"),
            **ADDRESS_FIELDS,
            "do_not_call": FieldDef("do_not_call", "bool", _("Do Not Call"), model_field="do_not_call"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["name"],
        search_fields=["name", "email_address", "phone_number", "title"],
        list_layout=["name", "account", "email_address", "phone_number", "assigned_user"],
        list_filter=["account", "do_not_call", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["salutation", "first_name", "last_name", "title", "account", "email_address", "phone_number", "do_not_call", "portal_user", "description"]},
            {"title": _("Address"), "fields": ["address_street", "address_city", "address_state", "address_country", "address_postal_code"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name", "email_address"],
        icon="contacts",
    )
)

registry.register(
    EntityDef(
        entity_type="Lead",
        model="crm.Lead",
        label=_("Lead"),
        label_plural=_("Leads"),
        fields={
            "salutation": FieldDef("salutation", "enum", _("Salutation"), options=list(Salutation.choices), model_field="salutation"),
            "first_name": FieldDef("first_name", "varchar", _("First Name"), model_field="first_name"),
            "last_name": FieldDef("last_name", "varchar", _("Last Name"), model_field="last_name"),
            "name": FieldDef("name", "varchar", _("Name"), model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(Lead.Status.choices), model_field="status"),
            "title": FieldDef("title", "varchar", _("Title"), model_field="title"),
            "source": FieldDef("source", "enum", _("Source"), options=list(LeadSource.choices), model_field="source"),
            "industry": FieldDef("industry", "enum", _("Industry"), options=list(Industry.choices), model_field="industry"),
            "opportunity_amount": FieldDef("opportunity_amount", "currency", _("Opportunity Amount"), model_field="opportunity_amount"),
            "opportunity_amount_converted": FieldDef("opportunity_amount_converted", "currency", _("Opportunity Amount (base)"), read_only=True, model_field="opportunity_amount_converted"),
            "website": FieldDef("website", "url", _("Website"), model_field="website"),
            "email_address": FieldDef("email_address", "email", _("Email"), model_field="email_address"),
            "phone_number": FieldDef("phone_number", "varchar", _("Phone"), model_field="phone_number"),
            **ADDRESS_FIELDS,
            "do_not_call": FieldDef("do_not_call", "bool", _("Do Not Call"), model_field="do_not_call"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "account_name": FieldDef("account_name", "varchar", _("Account Name"), model_field="account_name"),
            "converted_at": FieldDef("converted_at", "datetime", _("Converted At"), read_only=True, model_field="converted_at"),
            "created_account": FieldDef("created_account", "link", _("Created Account"), read_only=True, model_field="created_account"),
            "created_contact": FieldDef("created_contact", "link", _("Created Contact"), read_only=True, model_field="created_contact"),
            "created_opportunity": FieldDef("created_opportunity", "link", _("Created Opportunity"), read_only=True, model_field="created_opportunity"),
            **AUDIT_FIELDS,
        },
        ordering=["name"],
        search_fields=["name", "email_address", "phone_number", "account_name"],
        list_layout=["name", "status", "source", "email_address", "phone_number", "assigned_user"],
        list_filter=["status", "source", "industry", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["salutation", "first_name", "last_name", "status", "source", "industry", "title", "opportunity_amount", "opportunity_amount_converted", "email_address", "phone_number", "website", "account_name", "description"]},
            {"title": _("Address"), "fields": ["address_street", "address_city", "address_state", "address_country", "address_postal_code"]},
            {"title": _("Conversion"), "fields": ["converted_at", "created_account", "created_contact", "created_opportunity"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name", "email_address"],
        icon="person_add",
    )
)

registry.register(
    EntityDef(
        entity_type="Opportunity",
        model="crm.Opportunity",
        label=_("Opportunity"),
        label_plural=_("Opportunities"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "amount": FieldDef("amount", "currency", _("Amount"), model_field="amount"),
            "amount_weighted": FieldDef("amount_weighted", "currency", _("Weighted Amount"), read_only=True, model_field="amount_weighted"),
            "amount_converted": FieldDef("amount_converted", "currency", _("Amount (base)"), read_only=True, model_field="amount_converted"),
            "stage": FieldDef("stage", "enum", _("Stage"), options=list(OpportunityStage.choices), model_field="stage"),
            "last_stage": FieldDef("last_stage", "enum", _("Last Stage"), read_only=True, options=list(OpportunityStage.choices), model_field="last_stage"),
            "probability": FieldDef("probability", "int", _("Probability (%)"), model_field="probability"),
            "lead_source": FieldDef("lead_source", "enum", _("Lead Source"), options=list(LeadSource.choices), model_field="lead_source"),
            "close_date": FieldDef("close_date", "date", _("Close Date"), model_field="close_date"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "contact": FieldDef("contact", "link", _("Primary Contact"), model_field="contact"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name", "account__name", "contact__name"],
        list_layout=["name", "account", "stage", "amount", "probability", "close_date", "assigned_user"],
        list_filter=["stage", "lead_source", "account", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "account", "contact", "stage", "amount", "amount_converted", "amount_weighted", "probability", "last_stage", "lead_source", "close_date", "description"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name"],
        icon="trending_up",
    )
)

registry.register(
    EntityDef(
        entity_type="Task",
        model="crm.Task",
        label=_("Task"),
        label_plural=_("Tasks"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(TaskStatus.choices), model_field="status"),
            "priority": FieldDef("priority", "enum", _("Priority"), options=list(TaskPriority.choices), model_field="priority"),
            "date_start": FieldDef("date_start", "datetime", _("Start"), model_field="date_start"),
            "date_end": FieldDef("date_end", "datetime", _("End"), model_field="date_end"),
            "date_completed": FieldDef("date_completed", "datetime", _("Completed At"), read_only=True, model_field="date_completed"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "contact": FieldDef("contact", "link", _("Contact"), model_field="contact"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name", "description"],
        list_layout=["name", "status", "priority", "date_end", "assigned_user"],
        list_filter=["status", "priority", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "priority", "date_start", "date_end", "date_completed", "account", "contact", "description"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="task_alt",
    )
)

registry.register(
    EntityDef(
        entity_type="Call",
        model="crm.Call",
        label=_("Call"),
        label_plural=_("Calls"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(EventStatus.choices), model_field="status"),
            "date_start": FieldDef("date_start", "datetime", _("Start"), model_field="date_start"),
            "date_end": FieldDef("date_end", "datetime", _("End"), model_field="date_end"),
            "duration": FieldDef("duration", "int", _("Duration (s)"), model_field="duration"),
            "direction": FieldDef("direction", "enum", _("Direction"), options=list(CallDirection.choices), model_field="direction"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-date_start"],
        search_fields=["name", "description"],
        list_layout=["name", "status", "date_start", "direction", "assigned_user"],
        list_filter=["status", "direction", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "date_start", "date_end", "duration", "direction", "account", "description"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="call",
    )
)

registry.register(
    EntityDef(
        entity_type="Meeting",
        model="crm.Meeting",
        label=_("Meeting"),
        label_plural=_("Meetings"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(EventStatus.choices), model_field="status"),
            "date_start": FieldDef("date_start", "datetime", _("Start"), model_field="date_start"),
            "date_end": FieldDef("date_end", "datetime", _("End"), model_field="date_end"),
            "duration": FieldDef("duration", "int", _("Duration (s)"), model_field="duration"),
            "is_all_day": FieldDef("is_all_day", "bool", _("All Day"), model_field="is_all_day"),
            "join_url": FieldDef("join_url", "url", _("Join URL"), model_field="join_url"),
            "external_service": FieldDef("external_service", "varchar", _("External Service"), model_field="external_service"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-date_start"],
        search_fields=["name", "description"],
        list_layout=["name", "status", "date_start", "is_all_day", "assigned_user"],
        list_filter=["status", "is_all_day", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "date_start", "date_end", "duration", "is_all_day", "join_url", "external_service", "account", "description"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="event",
    )
)

registry.register(
    EntityDef(
        entity_type="Case",
        model="crm.Case",
        label=_("Case"),
        label_plural=_("Cases"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "number": FieldDef("number", "int", _("Number"), read_only=True, model_field="number"),
            "status": FieldDef("status", "enum", _("Status"), options=list(Case.Status.choices), model_field="status"),
            "priority": FieldDef("priority", "enum", _("Priority"), options=list(Case.Priority.choices), model_field="priority"),
            "type": FieldDef("type", "enum", _("Type"), options=list(Case.Type.choices), model_field="type"),
            "account": FieldDef("account", "link", _("Account"), model_field="account"),
            "contact": FieldDef("contact", "link", _("Contact"), model_field="contact"),
            "lead": FieldDef("lead", "link", _("Lead"), model_field="lead"),
            "is_internal": FieldDef("is_internal", "bool", _("Internal"), model_field="is_internal"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name", "description", "number"],
        list_layout=["number", "name", "status", "priority", "assigned_user"],
        list_filter=["status", "priority", "type", "account", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "number", "status", "priority", "type", "account", "contact", "lead", "is_internal", "description"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="support_agent",
    )
)

registry.register(
    EntityDef(
        entity_type="KnowledgeBaseArticle",
        model="crm.KnowledgeBaseArticle",
        label=_("Knowledge Base Article"),
        label_plural=_("Knowledge Base Articles"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(KnowledgeBaseArticle.Status.choices), model_field="status"),
            "language": FieldDef("language", "varchar", _("Language"), model_field="language"),
            "type": FieldDef("type", "varchar", _("Type"), model_field="type"),
            "publish_date": FieldDef("publish_date", "date", _("Publish Date"), model_field="publish_date"),
            "expiration_date": FieldDef("expiration_date", "date", _("Expiration Date"), model_field="expiration_date"),
            "order": FieldDef("order", "int", _("Order"), model_field="order"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "body": FieldDef("body", "text", _("Body"), model_field="body"),
            "body_plain": FieldDef("body_plain", "text", _("Body (plain)"), read_only=True, model_field="body_plain"),
            "categories": FieldDef("categories", "linkMultiple", _("Categories"), model_field="categories"),
            **AUDIT_FIELDS,
        },
        ordering=["order", "name"],
        search_fields=["name", "body", "description"],
        list_layout=["name", "status", "language", "publish_date", "assigned_user"],
        list_filter=["status", "language", "categories", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "language", "type", "categories", "publish_date", "expiration_date", "order", "description"]},
            {"title": _("Content"), "fields": ["body", "body_plain"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="menu_book",
    )
)

registry.register(
    EntityDef(
        entity_type="Document",
        model="crm.Document",
        label=_("Document"),
        label_plural=_("Documents"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "file": FieldDef("file", "file", _("File"), model_field="file"),
            "status": FieldDef("status", "enum", _("Status"), options=list(Document.Status.choices), model_field="status"),
            "type": FieldDef("type", "enum", _("Type"), options=list(Document.Type.choices), model_field="type"),
            "publish_date": FieldDef("publish_date", "date", _("Publish Date"), model_field="publish_date"),
            "expiration_date": FieldDef("expiration_date", "date", _("Expiration Date"), model_field="expiration_date"),
            "folder": FieldDef("folder", "link", _("Folder"), model_field="folder"),
            "accounts": FieldDef("accounts", "linkMultiple", _("Accounts"), model_field="accounts"),
            "contacts": FieldDef("contacts", "linkMultiple", _("Contacts"), model_field="contacts"),
            "leads": FieldDef("leads", "linkMultiple", _("Leads"), model_field="leads"),
            "opportunities": FieldDef("opportunities", "linkMultiple", _("Opportunities"), model_field="opportunities"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name", "description"],
        list_layout=["name", "status", "type", "folder", "publish_date", "assigned_user"],
        list_filter=["status", "type", "folder", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "file", "status", "type", "folder", "publish_date", "expiration_date", "description"]},
            {"title": _("Related"), "fields": ["accounts", "contacts", "leads", "opportunities"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="description",
    )
)

registry.register(
    EntityDef(
        entity_type="TargetList",
        model="crm.TargetList",
        label=_("Target List"),
        label_plural=_("Target Lists"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "category": FieldDef("category", "link", _("Category"), model_field="category"),
            **AUDIT_FIELDS,
        },
        ordering=["name"],
        search_fields=["name", "description"],
        list_layout=["name", "category", "assigned_user"],
        list_filter=["category", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "description", "category"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name"],
        icon="format_list_bulleted",
    )
)

registry.register(
    EntityDef(
        entity_type="Campaign",
        model="crm.Campaign",
        label=_("Campaign"),
        label_plural=_("Campaigns"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(Campaign.Status.choices), model_field="status"),
            "type": FieldDef("type", "enum", _("Type"), options=list(Campaign.Type.choices), model_field="type"),
            "start_date": FieldDef("start_date", "date", _("Start Date"), model_field="start_date"),
            "end_date": FieldDef("end_date", "date", _("End Date"), model_field="end_date"),
            "description": FieldDef("description", "text", _("Description"), model_field="description"),
            "target_lists": FieldDef("target_lists", "linkMultiple", _("Target Lists"), model_field="target_lists"),
            "sent_count": FieldDef("sent_count", "int", _("Sent"), read_only=True, model_field="sent_count"),
            "opened_count": FieldDef("opened_count", "int", _("Opened"), read_only=True, model_field="opened_count"),
            "clicked_count": FieldDef("clicked_count", "int", _("Clicked"), read_only=True, model_field="clicked_count"),
            "opted_out_count": FieldDef("opted_out_count", "int", _("Opted Out"), read_only=True, model_field="opted_out_count"),
            "bounced_count": FieldDef("bounced_count", "int", _("Bounced"), read_only=True, model_field="bounced_count"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name", "description"],
        list_layout=["name", "status", "type", "start_date", "assigned_user"],
        list_filter=["status", "type", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "type", "start_date", "end_date", "target_lists", "description"]},
            {"title": _("Metrics"), "fields": ["sent_count", "opened_count", "clicked_count", "opted_out_count", "bounced_count"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        duplicate_check_fields=["name"],
        icon="campaign",
    )
)

registry.register(
    EntityDef(
        entity_type="MassEmail",
        model="crm.MassEmail",
        label=_("Mass Email"),
        label_plural=_("Mass Emails"),
        fields={
            "name": FieldDef("name", "varchar", _("Name"), required=True, model_field="name"),
            "status": FieldDef("status", "enum", _("Status"), options=list(MassEmail.Status.choices), read_only=True, model_field="status"),
            "from_name": FieldDef("from_name", "varchar", _("From Name"), model_field="from_name"),
            "from_address": FieldDef("from_address", "email", _("From Address"), model_field="from_address"),
            "reply_to_address": FieldDef("reply_to_address", "email", _("Reply-To"), model_field="reply_to_address"),
            "start_at": FieldDef("start_at", "datetime", _("Start At"), model_field="start_at"),
            "email_template": FieldDef("email_template", "link", _("Email Template"), model_field="email_template"),
            "campaign": FieldDef("campaign", "link", _("Campaign"), model_field="campaign"),
            "target_lists": FieldDef("target_lists", "linkMultiple", _("Target Lists"), model_field="target_lists"),
            "opt_out_entirely": FieldDef("opt_out_entirely", "bool", _("Opt Out Entirely"), model_field="opt_out_entirely"),
            "store_sent_emails": FieldDef("store_sent_emails", "bool", _("Store Sent Emails"), model_field="store_sent_emails"),
            **AUDIT_FIELDS,
        },
        ordering=["-created_at"],
        search_fields=["name"],
        list_layout=["name", "status", "campaign", "start_at"],
        list_filter=["status", "campaign", "assigned_user"],
        detail_layout=[
            {"title": _("Overview"), "fields": ["name", "status", "campaign", "email_template", "target_lists", "start_at", "store_sent_emails", "opt_out_entirely"]},
            {"title": _("Sender"), "fields": ["from_name", "from_address", "reply_to_address"]},
            {"title": _("Assignment"), "fields": ["assigned_user", "teams", "created_at", "modified_at"]},
        ],
        stream=True,
        icon="mail",
    )
)

# Register lifecycle hooks (import has the side effect of registering them).
from omacrm.crm import hooks  # noqa: E402,F401

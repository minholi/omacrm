"""Customization demo data: custom fields, layouts, formulas, workflows, entity."""

from omacrm.core.models import (
    CustomEntity,
    CustomField,
    CustomLink,
    Formula,
    Layout,
    SavedFilter,
    Workflow,
)
from omacrm.core.services import relations
from omacrm.core.services.custom_entities import get_proxy

CUSTOM_FIELDS = (
    (
        "Account",
        "tier",
        "Tier",
        "enum",
        {"choices": [["Gold", "Gold"], ["Silver", "Silver"], ["Bronze", "Bronze"]]},
    ),
    ("Account", "is_strategic", "Strategic Account", "bool", {}),
    ("Contact", "linkedin_url", "LinkedIn", "url", {}),
    ("Lead", "lead_score", "Lead Score", "int", {}),
)

LAYOUTS = (
    (
        "Account",
        "list",
        ["name", "industry", "type", "phone_number", "assigned_user", "created_at"],
    ),
    (
        "Opportunity",
        "detail",
        [
            {
                "title": "Deal",
                "fields": ["name", "account", "contact", "amount", "stage", "probability", "close_date"],
            },
            {"title": "System", "fields": ["assigned_user", "created_at"]},
        ],
    ),
)

FORMULAS = (
    (
        "Lead score",
        "Lead",
        "before_save",
        'custom.lead_score = len(first_name or "") * 3 + len(last_name or "") * 2',
    ),
    (
        "Notify on win",
        "Opportunity",
        "after_save",
        'notify("Deal won: " + name) if stage == "Closed Won" else None',
    ),
)

WORKFLOWS = (
    (
        "Notify support on new case",
        "Case",
        "create",
        "",
        [{"type": "notify", "message": "A new case was created"}],
    ),
    (
        "Onboarding task on Closed Won",
        "Opportunity",
        "update",
        "stage == 'Closed Won'",
        [
            {
                "type": "create_record",
                "entity_type": "Task",
                "values": {"name": "Onboarding call", "priority": "High"},
            }
        ],
    ),
)

SAVED_FILTERS = (
    ("Hot opportunities", "Opportunity", {"stage": "Proposal"}),
    ("My started tasks", "Task", {"status": "Started"}),
    ("Urgent cases", "Case", {"priority": "Urgent"}),
)

PROJECTS = (
    ("Portal redesign", "Active", 25000),
    ("Data warehouse migration", "On Hold", 80000),
    ("Mobile app discovery", "Done", 15000),
)


def seed_customization(context):
    fields = {}
    for entity_type, name, label, field_type, params in CUSTOM_FIELDS:
        field, _ = CustomField.objects.get_or_create(
            entity_type=entity_type,
            name=name,
            defaults={
                "label": label,
                "field_type": field_type,
                "params": params,
            },
        )
        fields[f"{entity_type}.{name}"] = field

    layouts = {}
    for entity_type, layout_name, data in LAYOUTS:
        layout, _ = Layout.objects.get_or_create(
            entity_type=entity_type,
            layout_name=layout_name,
            defaults={"data": data, "is_custom": True},
        )
        layouts[f"{entity_type}.{layout_name}"] = layout

    formulas = {}
    for name, entity_type, event, script in FORMULAS:
        formula, _ = Formula.objects.get_or_create(
            entity_type=entity_type,
            event=event,
            script=script,
            defaults={"description": name},
        )
        formulas[name] = formula

    for lead in context["leads"]:
        if "lead_score" not in (lead.custom_data or {}):
            lead.save()

    account = context["accounts"]["Horizonte Energia"]
    account.custom_data = {
        **(account.custom_data or {}),
        "tier": "Bronze",
        "is_strategic": False,
    }
    account.save(update_fields=["custom_data"])
    strategic = context["accounts"]["Acme Corp"]
    strategic.custom_data = {
        **(strategic.custom_data or {}),
        "tier": "Gold",
        "is_strategic": True,
    }
    strategic.save(update_fields=["custom_data"])
    context["contacts"]["olivia.brown@acme.example"].custom_data = {
        "linkedin_url": "https://www.linkedin.com/in/olivia-brown-demo"
    }
    context["contacts"]["olivia.brown@acme.example"].save(
        update_fields=["custom_data"]
    )

    workflows = {}
    for name, entity_type, event, condition, actions in WORKFLOWS:
        workflow, _ = Workflow.objects.get_or_create(
            name=name,
            defaults={
                "entity_type": entity_type,
                "event": event,
                "condition": condition,
                "actions": actions,
                "is_active": True,
            },
        )
        workflows[name] = workflow

    from omacrm.crm.models import Case, Opportunity, Task

    if not Case.objects.filter(name="Welcome aboard TechBrasil").exists():
        Case.objects.create(
            name="Welcome aboard TechBrasil",
            status="New",
            priority="Normal",
            type="Question",
            contact=context["portal_contact"],
            account=context["portal_account"],
            assigned_user=context["carla"],
            description="Triggered demo case for the new-case workflow.",
        )

    greenleaf = Opportunity.objects.filter(name="GreenLeaf supply chain").first()
    if greenleaf is not None and not Task.objects.filter(name="Onboarding call").exists():
        greenleaf.description = (greenleaf.description or "") + " Closed won on demo day."
        greenleaf.save()

    for name, entity_type, params in SAVED_FILTERS:
        SavedFilter.objects.get_or_create(
            user=context["demo"],
            entity_type=entity_type,
            name=name,
            defaults={"params": params},
        )

    project_entity, _ = CustomEntity.objects.get_or_create(
        name="Project",
        defaults={
            "label": "Project",
            "label_plural": "Projects",
            "description": "Demo custom entity seeded by seed_demo.",
            "icon": "architecture",
            "menu_order": 10,
            "is_active": True,
        },
    )
    CustomField.objects.get_or_create(
        entity_type="Project",
        name="status",
        defaults={
            "label": "Status",
            "field_type": "enum",
            "params": {
                "choices": [["Active", "Active"], ["On Hold", "On Hold"], ["Done", "Done"]]
            },
        },
    )
    CustomField.objects.get_or_create(
        entity_type="Project",
        name="budget",
        defaults={"label": "Budget", "field_type": "currency"},
    )
    CustomLink.objects.get_or_create(
        entity_type="Project",
        name="account",
        defaults={
            "link_type": "belongsTo",
            "link_entity": "Account",
            "label": "Account",
        },
    )
    CustomLink.objects.get_or_create(
        entity_type="Project",
        name="contacts",
        defaults={
            "link_type": "manyToMany",
            "link_entity": "Contact",
            "label": "Team",
        },
    )

    proxy = get_proxy(project_entity.name)
    projects = []
    if proxy.objects.count() == 0:
        for name, status, budget in PROJECTS:
            projects.append(
                proxy.objects.create(
                    entity_type=project_entity.name,
                    name=name,
                    assigned_user=context["demo"],
                    custom_data={"status": status, "budget": budget},
                )
            )

    all_projects = list(proxy.objects.all())
    accounts = list(context["accounts"].values())
    contacts = list(context["contacts"].values())
    for index, project in enumerate(all_projects):
        relations.set_related(project, "account", [accounts[index % len(accounts)]])
        if len(contacts) >= 2:
            relations.set_related(
                project,
                "contacts",
                [
                    contacts[(index * 2) % len(contacts)],
                    contacts[(index * 2 + 1) % len(contacts)],
                ],
            )

    context.update(
        {
            "custom_fields": fields,
            "layouts": layouts,
            "formulas": formulas,
            "workflows": workflows,
            "project_entity": project_entity,
            "projects": all_projects,
        }
    )

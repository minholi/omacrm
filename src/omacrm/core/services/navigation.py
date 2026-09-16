"""Dynamic Unfold sidebar navigation.

Unfold resolves ``UNFOLD["SIDEBAR"]["navigation"]`` per request, so returning a
dotted callback here lets runtime custom entities appear in the menu without a
server restart (they still need the admin materialized, which happens at
startup and whenever a ``CustomEntity`` is saved).
"""

from django.db import OperationalError, ProgrammingError
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _


def _group(title, items, *, collapsible=True, separator=False):
    return {
        "title": title,
        "collapsible": collapsible,
        "separator": separator,
        "items": items,
    }


def _item(title, icon, url_name, **extra):
    item = {"title": title, "icon": icon, "link": reverse(url_name)}
    item.update(extra)
    return item


def _custom_entity_items(request):
    from django.contrib import admin

    from omacrm.core.models import CustomEntity
    from omacrm.core.services.custom_entities import get_proxy

    try:
        entities = list(
            CustomEntity.objects.filter(is_active=True, show_in_menu=True).order_by(
                "menu_order", "name"
            )
        )
    except (OperationalError, ProgrammingError):
        return []

    items = []
    for entity in entities:
        model = get_proxy(entity.name)
        model_admin = admin.site._registry.get(model)
        if (
            model_admin is not None
            and request is not None
            and not model_admin.has_view_permission(request)
        ):
            continue
        meta = model._meta
        url_name = f"admin:{meta.app_label}_{meta.model_name}_changelist"
        try:
            link = reverse(url_name)
        except NoReverseMatch:
            continue
        items.append(
            {
                "title": entity.display_label_plural,
                "icon": entity.icon or "extension",
                "link": link,
            }
        )
    return items


def sidebar_navigation(request=None):
    """Full sidebar navigation list (built-in groups + custom entities)."""

    navigation = [
        _group(
            _("Sales"),
            [
                _item(_("Accounts"), "domain", "admin:crm_account_changelist"),
                _item(_("Contacts"), "contacts", "admin:crm_contact_changelist"),
                _item(_("Leads"), "person_add", "admin:crm_lead_changelist"),
                _item(
                    _("Opportunities"),
                    "trending_up",
                    "admin:crm_opportunity_changelist",
                ),
                _item(_("Tasks"), "task_alt", "admin:crm_task_changelist"),
                _item(_("Documents"), "description", "admin:crm_document_changelist"),
            ],
            separator=True,
        ),
        _group(
            _("Support"),
            [
                _item(_("Cases"), "support_agent", "admin:crm_case_changelist"),
                _item(
                    _("Knowledge Base"),
                    "menu_book",
                    "admin:crm_knowledgebasearticle_changelist",
                ),
            ],
        ),
        _group(
            _("Marketing"),
            [
                _item(_("Campaigns"), "campaign", "admin:crm_campaign_changelist"),
                _item(
                    _("Target Lists"),
                    "format_list_bulleted",
                    "admin:crm_targetlist_changelist",
                ),
                _item(_("Mass Emails"), "mail", "admin:crm_massemail_changelist"),
                _item(
                    _("Email Templates"),
                    "draft",
                    "admin:crm_emailtemplate_changelist",
                ),
                _item(
                    _("Lead Capture"), "webhook", "admin:crm_leadcapture_changelist"
                ),
            ],
        ),
        _group(
            _("Activities"),
            [
                _item(_("Calendar"), "calendar_month", "crm_calendar"),
                _item(_("Calls"), "call", "admin:crm_call_changelist"),
                _item(_("Meetings"), "event", "admin:crm_meeting_changelist"),
                _item(_("Emails"), "mail", "admin:core_email_changelist"),
            ],
        ),
        _group(
            _("Administration"),
            [
                _item(_("Global Search"), "search", "global_search"),
                _item(_("Users"), "person", "admin:core_user_changelist"),
                _item(_("Teams"), "groups", "admin:core_team_changelist"),
                _item(_("Roles"), "shield_person", "admin:core_role_changelist"),
                _item(_("Preferences"), "tune", "admin:core_preferences_changelist"),
            ],
            separator=True,
        ),
        _group(
            _("Customization"),
            [
                _item(
                    _("Custom Fields"),
                    "add_box",
                    "admin:core_customfield_changelist",
                ),
                _item(_("Layouts"), "view_column", "admin:core_layout_changelist"),
                _item(
                    _("Layout Editor"),
                    "dashboard_customize",
                    "layout_editor_index",
                ),
                _item(
                    _("Custom Entities"),
                    "extension",
                    "admin:core_customentity_changelist",
                ),
                _item(_("Formulas"), "function", "admin:core_formula_changelist"),
                _item(
                    _("Dynamic Logic"),
                    "visibility",
                    "admin:core_dynamiclogic_changelist",
                ),
                _item(
                    _("Workflows"), "account_tree", "admin:core_workflow_changelist"
                ),
            ],
        ),
        _group(
            _("System"),
            [
                _item(_("Jobs"), "pending_actions", "admin:core_job_changelist"),
                _item(
                    _("Scheduled Jobs"),
                    "schedule",
                    "admin:core_scheduledjob_changelist",
                ),
                _item(
                    _("Email Accounts"),
                    "inbox",
                    "admin:core_emailaccount_changelist",
                ),
                _item(
                    _("Currencies"), "currency_exchange", "admin:core_currency_changelist"
                ),
                _item(_("Webhooks"), "webhook", "admin:core_webhook_changelist"),
                _item(_("Notes"), "forum", "admin:core_note_changelist"),
                _item(
                    _("Notifications"),
                    "notifications",
                    "admin:core_notification_changelist",
                ),
                _item(
                    _("Settings"), "settings", "admin:constance_config_changelist"
                ),
            ],
        ),
    ]

    custom_items = _custom_entity_items(request)
    if custom_items:
        navigation.append(
            _group(_("Custom entities"), custom_items, separator=True)
        )
    return navigation

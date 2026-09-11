"""Custom entries injected into the Unfold command palette."""

from urllib.parse import urlencode

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from unfold.dataclasses import SearchResult

STATIC_COMMANDS = (
    (
        "Calendar",
        _("Month calendar and agenda"),
        "calendar_month",
        "crm_calendar",
        False,
    ),
    (
        "Global search",
        _("Search across every entity"),
        "search",
        "global_search",
        False,
    ),
    (
        "Layout editor",
        _("Customize list columns and detail sections"),
        "dashboard_customize",
        "layout_editor_index",
        False,
    ),
    (
        "Email templates",
        _("Design and edit email templates"),
        "draft",
        "admin:crm_emailtemplate_changelist",
        True,
    ),
    (
        "Custom entities",
        _("Manage runtime custom entities"),
        "category",
        "admin:core_customentity_changelist",
        True,
    ),
    (
        "Roles & access",
        _("Edit role scopes and field-level access"),
        "admin_panel_settings",
        "admin:core_role_changelist",
        True,
    ),
)


def _matches(term: str, *values) -> bool:
    return any(term in str(value).lower() for value in values if value)


def _admin_for(request, entity_type: str):
    from omacrm.core.metadata.registry import registry

    if not registry.has(entity_type):
        return None, None
    model = registry.model_for(entity_type)
    model_admin = admin.site._registry.get(model) if model is not None else None
    if model_admin is None or not model_admin.has_view_permission(request):
        return model_admin, None
    meta = model._meta
    names = {
        "changelist": f"admin:{meta.app_label}_{meta.model_name}_changelist",
        "add": f"admin:{meta.app_label}_{meta.model_name}_add",
    }
    return model_admin, names


def _static_commands(request, term: str) -> list[SearchResult]:
    results = []
    for title, description, icon, url_name, staff_only in STATIC_COMMANDS:
        if staff_only and not request.user.is_superuser:
            continue
        if not _matches(term, title, description):
            continue
        try:
            link = reverse(url_name)
        except NoReverseMatch:
            continue
        results.append(
            SearchResult(
                title=str(title), description=str(description), link=link, icon=icon
            )
        )
    return results


def _entity_shortcuts(request, term: str) -> list[SearchResult]:
    from omacrm.core.metadata.registry import registry

    results = []
    for entity_type in registry.entity_types():
        entity = registry.get(entity_type)
        labels = (
            entity.label,
            entity.display_label,
            entity.display_label_plural,
            entity_type,
        )
        if not _matches(term, *labels):
            continue
        model_admin, names = _admin_for(request, entity_type)
        if model_admin is None or names is None:
            continue
        try:
            changelist = reverse(names["changelist"])
        except NoReverseMatch:
            continue
        results.append(
            SearchResult(
                title=str(entity.display_label_plural),
                description=str(_("Open list")),
                link=changelist,
                icon="list",
            )
        )
        if model_admin.has_add_permission(request):
            try:
                add_link = reverse(names["add"])
            except NoReverseMatch:
                continue
            results.append(
                SearchResult(
                    title=str(_("New %(entity)s") % {"entity": entity.display_label}),
                    description=str(_("Create record")),
                    link=add_link,
                    icon="add_circle",
                )
            )
    return results


def _saved_filters(request, term: str) -> list[SearchResult]:
    from omacrm.core.models import SavedFilter

    results = []
    try:
        saved_filters = SavedFilter.objects.filter(user=request.user)[:50]
    except Exception:  # noqa: BLE001 - table may be unavailable during setup
        return results

    for saved in saved_filters:
        if not _matches(term, saved.name, saved.entity_type):
            continue
        _model_admin, names = _admin_for(request, saved.entity_type)
        if names is None:
            continue
        try:
            link = reverse(names["changelist"])
        except NoReverseMatch:
            continue
        query = urlencode(saved.params or {}, doseq=True)
        if query:
            link = f"{link}?{query}"
        results.append(
            SearchResult(
                title=saved.name,
                description=str(_("Saved filter · %(entity)s") % {"entity": saved.entity_type}),
                link=link,
                icon="filter_list",
            )
        )
    return results


def command_search(request, search_term) -> list[SearchResult]:
    """Unfold ``COMMAND.search_callback``: extra palette results."""

    term = (search_term or "").strip().lower()
    if not term:
        return []

    results: list[SearchResult] = []
    results.extend(_static_commands(request, term))
    results.extend(_entity_shortcuts(request, term))
    results.extend(_saved_filters(request, term))

    seen = set()
    unique = []
    for result in results:
        key = (result.title, result.link)
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique[:20]

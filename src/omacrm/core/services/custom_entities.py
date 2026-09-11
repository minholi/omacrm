"""Runtime-defined custom entities backed by ``DynamicRecord``.

Each active ``CustomEntity`` gets a proxy model and its own admin, reusing the
metadata/custom-field machinery. Adding new custom fields after creation is
supported (values live in ``custom_data``); an API endpoint requires a restart
because the router is built at startup.
"""

import logging

from omacrm.core.metadata.registry import registry

logger = logging.getLogger(__name__)

_proxies: dict[str, type] = {}

ENTITY_TEMPLATES = {
    "base": {},
    "person": {
        "icon": "person",
        "fields": (
            (
                "salutation",
                "Salutation",
                "enum",
                {"choices": [["Mr.", "Mr."], ["Ms.", "Ms."], ["Mrs.", "Mrs."], ["Dr.", "Dr."]]},
            ),
            ("first_name", "First Name", "varchar", {}),
            ("last_name", "Last Name", "varchar", {}),
            ("title", "Job Title", "varchar", {}),
            ("email_address", "Email", "email", {}),
            ("phone_number", "Phone", "phone", {}),
            ("address", "Address", "address", {}),
        ),
        "list": ["name", "title", "email_address", "phone_number"],
        "detail": [
            {
                "title": "Identity",
                "fields": ["name", "salutation", "first_name", "last_name"],
            },
            {
                "title": "Contact",
                "fields": ["title", "email_address", "phone_number", "address"],
            },
        ],
    },
    "company": {
        "icon": "domain",
        "fields": (
            ("email_address", "Email", "email", {}),
            ("phone_number", "Phone", "phone", {}),
            ("website", "Website", "url", {}),
            ("industry", "Industry", "varchar", {}),
            ("billing_address", "Billing Address", "address", {}),
        ),
        "list": ["name", "email_address", "phone_number", "website"],
        "detail": [
            {
                "title": "Overview",
                "fields": ["name", "email_address", "phone_number", "website", "industry"],
            },
            {"title": "Address", "fields": ["billing_address"]},
        ],
    },
    "event": {
        "icon": "event",
        "show_in_calendar": True,
        "fields": (
            (
                "status",
                "Status",
                "enum",
                {"choices": [["Planned", "Planned"], ["Held", "Held"], ["Not Held", "Not Held"]]},
            ),
            ("date_start", "Start", "datetime", {}),
            ("date_end", "End", "datetime", {}),
            ("location", "Location", "varchar", {}),
            ("description", "Notes", "text", {}),
        ),
        "list": ["name", "status", "date_start", "date_end"],
        "detail": [
            {
                "title": "Schedule",
                "fields": ["name", "status", "date_start", "date_end", "location"],
            },
            {"title": "Notes", "fields": ["description"]},
        ],
    },
}


def apply_template(custom_entity) -> None:
    """Create the initial fields and layouts of an entity template."""

    spec = ENTITY_TEMPLATES.get(custom_entity.template or "base")
    if not spec:
        return

    from omacrm.core.models import CustomField, Layout

    updates = []
    if spec.get("icon") and (custom_entity.icon in {"", "extension"}):
        custom_entity.icon = spec["icon"]
        updates.append("icon")
    if spec.get("show_in_calendar") and not custom_entity.show_in_calendar:
        custom_entity.show_in_calendar = True
        updates.append("show_in_calendar")
    if updates:
        custom_entity.save(update_fields=updates)

    for name, label, field_type, params in spec.get("fields", ()):
        CustomField.objects.get_or_create(
            entity_type=custom_entity.name,
            name=name,
            defaults={"label": label, "field_type": field_type, "params": params},
        )
    if spec.get("list"):
        Layout.objects.get_or_create(
            entity_type=custom_entity.name,
            layout_name="list",
            defaults={"data": list(spec["list"]), "is_custom": True},
        )
    if spec.get("detail"):
        Layout.objects.get_or_create(
            entity_type=custom_entity.name,
            layout_name="detail",
            defaults={"data": spec["detail"], "is_custom": True},
        )


def _connect_person_name(model) -> None:
    from django.db.models.signals import pre_save

    def receiver(sender, instance, **kwargs):
        data = instance.custom_data or {}
        first = data.get("first_name") or ""
        last = data.get("last_name") or ""
        if first or last:
            instance.name = f"{first} {last}".strip()

    pre_save.connect(
        receiver,
        sender=model,
        dispatch_uid=f"omacrm.custom_entity.person_name.{model._meta.model_name}",
        weak=False,
    )


def get_proxy(entity_name: str):
    if entity_name in _proxies:
        return _proxies[entity_name]

    from django.apps import apps

    proxy = None
    try:
        proxy = apps.get_model("core", entity_name)
    except LookupError:
        proxy = None

    if proxy is None:
        from omacrm.core.models import DynamicRecord

        meta = type(
            "Meta",
            (),
            {
                "app_label": "core",
                "proxy": True,
                "auto_created": True,
                "verbose_name": entity_name,
                "ordering": ["-created_at"],
            },
        )
        proxy = type(
            entity_name,
            (DynamicRecord,),
            {
                "__module__": "omacrm.core.dynamic",
                "Meta": meta,
                "entity_type": entity_name,
            },
        )

    _proxies[entity_name] = proxy
    return proxy


def materialize(custom_entity):
    """Build the proxy model, admin and hook wiring for a custom entity."""

    from django.contrib import admin as django_admin
    from django.contrib.contenttypes.models import ContentType

    from omacrm.core.admin.dynamic import dynamic_admin_for
    from omacrm.core.services.hooks import hooks

    name = custom_entity.name
    proxy = get_proxy(name)

    try:
        # The CT manager caches model -> content type lookups; a previous
        # unregister may have deleted the row, so never trust a stale entry.
        ContentType.objects.clear_cache()
        ContentType.objects.get_for_model(proxy, for_concrete_model=False)
    except Exception:  # noqa: BLE001 - DB may be unavailable during setup
        logger.debug("Could not ensure content type for %s", name, exc_info=True)

    if not django_admin.site.is_registered(proxy):
        django_admin.site.register(proxy, dynamic_admin_for(name))

    from omacrm.core.models import CustomEntity

    if custom_entity.template == CustomEntity.Template.PERSON:
        _connect_person_name(proxy)

    hooks.connect_entity(name, proxy)
    registry.invalidate()
    return proxy


def _purge_stale_content_types() -> None:
    """Delete content types whose model class no longer exists.

    Prevents dangling generic relations (stream notes, attachments) from
    crashing pages after a custom entity was removed.
    """

    from django.contrib.contenttypes.models import ContentType

    try:
        stale = [
            content_type.pk
            for content_type in ContentType.objects.filter(app_label="core")
            if content_type.model_class() is None
        ]
    except Exception:  # noqa: BLE001 - DB may be unavailable during setup
        return

    if stale:
        ContentType.objects.filter(pk__in=stale).delete()
        ContentType.objects.clear_cache()


def unregister(custom_entity) -> None:
    from django.contrib import admin as django_admin
    from django.contrib.contenttypes.models import ContentType

    name = custom_entity.name
    proxy = _proxies.pop(name, None)
    if proxy is None:
        from django.apps import apps

        try:
            proxy = apps.get_model("core", name)
        except LookupError:
            proxy = None

    if proxy is not None:
        try:
            content_type = ContentType.objects.filter(
                app_label="core", model=proxy._meta.model_name
            ).first()
            if content_type is not None:
                # Cascades to stream notes, attachments and notifications.
                content_type.delete()
            # The CT manager caches model -> content type lookups; clear it so
            # recreating the entity later does not reuse a deleted row.
            ContentType.objects.clear_cache()
        except Exception:  # noqa: BLE001
            logger.exception("Could not remove content type for %s", name)

        if django_admin.site.is_registered(proxy):
            django_admin.site.unregister(proxy)

    registry.unregister(name)
    registry.invalidate()

    try:
        from django.db.models import Q

        from omacrm.core.models import CustomLink
        from omacrm.core.services import relations

        relations.delete_links_for_entity(name)
        CustomLink.objects.filter(Q(entity_type=name) | Q(link_entity=name)).delete()
    except Exception:  # noqa: BLE001 - cleanup is best effort
        logger.exception("Could not remove links of custom entity %s", name)


def sync(custom_entity, created: bool = False) -> None:
    """Called on CustomEntity save: register or unregister accordingly."""

    try:
        if custom_entity.is_active:
            if created:
                apply_template(custom_entity)
            materialize(custom_entity)
        else:
            unregister(custom_entity)
        _refresh_urlconf()
    except Exception:  # noqa: BLE001 - never break the admin save
        logger.exception("Failed to sync custom entity %s", custom_entity.name)


def _refresh_urlconf() -> None:
    """Rebuild the URLconf so a new admin resolves without a restart."""

    try:
        import importlib

        import omacrm.config.urls
        from django.urls import clear_url_caches

        importlib.reload(omacrm.config.urls)
        clear_url_caches()
    except Exception:  # noqa: BLE001 - best effort during setup
        logger.debug("Could not refresh URLconf", exc_info=True)


def ensure_all() -> None:
    """Materialize active custom entities at startup."""

    from omacrm.core.models import CustomEntity

    _purge_stale_content_types()

    try:
        entities = list(CustomEntity.objects.filter(is_active=True))
    except Exception:  # noqa: BLE001 - tables may not exist yet
        return

    for entity in entities:
        try:
            materialize(entity)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to materialize custom entity %s", entity.name)

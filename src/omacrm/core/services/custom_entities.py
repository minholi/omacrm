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


def sync(custom_entity) -> None:
    """Called on CustomEntity save: register or unregister accordingly."""

    try:
        if custom_entity.is_active:
            materialize(custom_entity)
        else:
            unregister(custom_entity)
    except Exception:  # noqa: BLE001 - never break the admin save
        logger.exception("Failed to sync custom entity %s", custom_entity.name)


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

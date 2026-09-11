from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "omacrm.core"
    label = "core"
    verbose_name = "Core"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from omacrm.core.metadata.registry import registry
        from omacrm.core.models import (
            CustomEntity,
            CustomField,
            CustomLink,
            Formula,
            Layout,
            Workflow,
        )
        from omacrm.core.services import custom_entities, formula
        from omacrm.core.services.hooks import hooks

        def _invalidate_metadata(sender, instance, **kwargs):
            registry.invalidate()

        for model in (CustomField, CustomLink, Layout):
            label = model._meta.label
            post_save.connect(
                _invalidate_metadata,
                sender=model,
                dispatch_uid=f"omacrm.metadata.invalidate.save.{label}",
                weak=False,
            )
            post_delete.connect(
                _invalidate_metadata,
                sender=model,
                dispatch_uid=f"omacrm.metadata.invalidate.delete.{label}",
                weak=False,
            )

        def _invalidate_formulas(sender, instance, **kwargs):
            formula.invalidate_formula_cache()

        for model in (Formula, Workflow):
            label = model._meta.label
            post_save.connect(
                _invalidate_formulas,
                sender=model,
                dispatch_uid=f"omacrm.formula.invalidate.save.{label}",
                weak=False,
            )
            post_delete.connect(
                _invalidate_formulas,
                sender=model,
                dispatch_uid=f"omacrm.formula.invalidate.delete.{label}",
                weak=False,
            )

        def _sync_custom_entity(sender, instance, created=False, **kwargs):
            custom_entities.sync(instance, created=created)

        def _remove_custom_entity(sender, instance, **kwargs):
            custom_entities.unregister(instance)

        post_save.connect(
            _sync_custom_entity,
            sender=CustomEntity,
            dispatch_uid="omacrm.custom_entity.sync",
            weak=False,
        )
        post_delete.connect(
            _remove_custom_entity,
            sender=CustomEntity,
            dispatch_uid="omacrm.custom_entity.remove",
            weak=False,
        )

        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=(
                    "Accessing the database during app initialization is "
                    "discouraged.*"
                ),
                category=RuntimeWarning,
            )
            custom_entities.ensure_all()
            hooks.connect_signals()

        from djmoney.contrib.django_rest_framework import register_money_field

        register_money_field()

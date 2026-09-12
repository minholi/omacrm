from collections import defaultdict


class HookRegistry:
    """Convention-based lifecycle hooks for record types.

    Hooks are registered per entity type and event (``before_save``,
    ``after_save``, ``before_delete``, ``after_delete``) and invoked from
    Django signal receivers wired in :meth:`connect_signals`.
    """

    EVENTS = ("before_save", "after_save", "before_delete", "after_delete")

    def __init__(self):
        self._hooks: dict[tuple[str, str], list[tuple[int, callable]]] = defaultdict(list)
        self._connected = False
        # Signals use weak references by default; keep our closures alive.
        self._receivers: list = []

    def register(self, entity_type: str, event: str, order: int = 9):
        if event not in self.EVENTS:
            raise ValueError(f"Unknown hook event: {event}")

        def decorator(func):
            self._hooks[(entity_type, event)].append((order, func))
            self._hooks[(entity_type, event)].sort(key=lambda item: item[0])
            return func

        return decorator

    def get(self, entity_type: str, event: str):
        return [func for _, func in self._hooks.get((entity_type, event), [])]

    def call(self, entity_type: str, event: str, instance, **kwargs):
        for func in self.get(entity_type, event):
            func(instance=instance, **kwargs)

    # -- signal wiring ------------------------------------------------------

    @staticmethod
    def _receiver(event: str, entity_type: str):
        def receiver(sender, instance, **kwargs):
            hooks.call(entity_type, event, instance, **kwargs)

        return receiver

    def connect_signals(self):
        if self._connected:
            return

        from django.apps import apps as django_apps

        from omacrm.core.metadata.registry import registry
        from omacrm.core.services import custom_entities

        for entity_type, entity_def in registry.entities().items():
            if entity_def.dynamic:
                model = custom_entities.get_proxy(entity_type)
            else:
                try:
                    model = django_apps.get_model(entity_def.model)
                except LookupError:
                    continue
            self.connect_entity(entity_type, model)

        self._connected = True

    def connect_entity(self, entity_type: str, model) -> None:
        """Connect lifecycle receivers for one entity type/model class."""

        from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

        from omacrm.core.services import stream

        receivers = [
            self._before_save_receiver(entity_type, stream),
            self._after_save_receiver(entity_type, stream),
            self._receiver("before_delete", entity_type),
            self._after_delete_receiver(entity_type),
        ]
        self._receivers.extend(receivers)

        pre_save.connect(
            receivers[0],
            sender=model,
            dispatch_uid=f"omacrm.hooks.pre_save.{entity_type}",
            weak=False,
        )
        post_save.connect(
            receivers[1],
            sender=model,
            dispatch_uid=f"omacrm.hooks.post_save.{entity_type}",
            weak=False,
        )
        pre_delete.connect(
            receivers[2],
            sender=model,
            dispatch_uid=f"omacrm.hooks.pre_delete.{entity_type}",
            weak=False,
        )
        post_delete.connect(
            receivers[3],
            sender=model,
            dispatch_uid=f"omacrm.hooks.post_delete.{entity_type}",
            weak=False,
        )

    def _before_save_receiver(self, entity_type: str, stream_module):
        def receiver(sender, instance, **kwargs):
            stream_module.snapshot(instance)

            from omacrm.core.services import formula

            formula.run_formulas(instance, "before_save")
            hooks.call(entity_type, "before_save", instance, **kwargs)

        return receiver

    def _after_save_receiver(self, entity_type: str, stream_module):
        def receiver(sender, instance, created=False, **kwargs):
            stream_module.on_save(instance, created=created)

            if created:
                from omacrm.core.services import subscriptions

                subscriptions.auto_follow_created(instance)

            from omacrm.core.services import formula, webhooks, workflows

            formula.run_formulas(instance, "after_save")
            hooks.call(entity_type, "after_save", instance, created=created, **kwargs)

            if getattr(instance, "deleted", False):
                event = "delete"
            elif created:
                event = "create"
            else:
                event = "update"

            workflows.run_workflows(instance, event)
            webhooks.enqueue_event(instance, event)

        return receiver

    def _after_delete_receiver(self, entity_type: str):
        def receiver(sender, instance, **kwargs):
            hooks.call(entity_type, "after_delete", instance, **kwargs)

            from omacrm.core.services import webhooks

            webhooks.enqueue_event(instance, "delete")

        return receiver


hooks = HookRegistry()

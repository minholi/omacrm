from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Formula(models.Model):
    """A small script executed before/after save on an entity type.

    Supports assignments (``field = expression``) and expression statements.
    The expression language is a safe AST-restricted subset of Python.
    """

    class Event(models.TextChoices):
        BEFORE_SAVE = "before_save", _("Before Save")
        AFTER_SAVE = "after_save", _("After Save")

    entity_type = models.CharField(max_length=64, db_index=True)
    event = models.CharField(max_length=20, choices=Event.choices)
    script = models.TextField(
        help_text=_(
            "One statement per line, e.g. `probability = 50` or "
            "`notify('Deal updated')`."
        )
    )
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_type", "event", "order", "id"]
        verbose_name_plural = "formulas"

    def __str__(self):
        return f"{self.entity_type}:{self.event} #{self.pk or ''}"

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry

        if self.entity_type and not registry.has(self.entity_type):
            raise ValidationError({"entity_type": _("Unknown entity type.")})
        if self.entity_type and registry.has(self.entity_type):
            # Validate the script against the entity fields in a dry run.
            from omacrm.core.services.formula import FormulaError, interpret

            model = registry.model_for(self.entity_type)
            instance = model()
            try:
                interpret(self.script, instance, dry_run=True)
            except FormulaError as exc:
                raise ValidationError({"script": str(exc)}) from exc


class Workflow(models.Model):
    """Trigger → condition → actions automation rule."""

    class Event(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        DELETE = "delete", _("Delete")

    class ActionType(models.TextChoices):
        SET_FIELD = "set_field", _("Set field")
        NOTIFY = "notify", _("Notify assigned user")
        CREATE_RECORD = "create_record", _("Create record")
        SEND_EMAIL = "send_email", _("Send email")

    name = models.CharField(max_length=255, unique=True)
    entity_type = models.CharField(max_length=64, db_index=True)
    event = models.CharField(max_length=20, choices=Event.choices)
    condition = models.TextField(
        blank=True,
        default="",
        help_text=_("Optional expression, e.g. `stage == 'Closed Won'`."),
    )
    actions = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            'List of actions, e.g. [{"type": "set_field", "field": "priority", "value": "High"}].'
        ),
    )
    description = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_type", "event", "order", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry

        errors = {}
        if self.entity_type and not registry.has(self.entity_type):
            errors["entity_type"] = _("Unknown entity type.")
        elif self.entity_type:
            model = registry.model_for(self.entity_type)
            field_names = {field.name for field in model._meta.get_fields()}
            actions = self.actions or []
            if not isinstance(actions, list):
                errors["actions"] = _("Actions must be a list.")
            else:
                for index, action in enumerate(actions):
                    if not isinstance(action, dict) or action.get("type") not in self.ActionType.values:
                        errors["actions"] = _(
                            "Action #%(index)s is invalid." % {"index": index + 1}
                        )
                        break
                    if action.get("type") == self.ActionType.SET_FIELD:
                        if action.get("field") not in field_names:
                            errors["actions"] = _(
                                "Action #%(index)s references an unknown field."
                                % {"index": index + 1}
                            )
                            break
        if errors:
            raise ValidationError(errors)

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


class DynamicLogic(models.Model):
    """Condition-driven field state (visible / required / read-only).

    The condition tree mirrors EspoCRM's vocabulary: a node is either a leaf
    (``{"type": "equals", "attribute": "status", "value": "Open"}``) or a
    group (``and``/``or`` with a list ``value``, ``not`` with a single child).
    """

    class Action(models.TextChoices):
        VISIBLE = "visible", _("Visible")
        REQUIRED = "required", _("Required")
        READONLY = "readonly", _("Read-only")

    entity_type = models.CharField(max_length=64, db_index=True)
    field_name = models.CharField(max_length=64)
    action = models.CharField(max_length=20, choices=Action.choices)
    condition = models.JSONField(
        default=dict,
        help_text=_(
            "Condition tree, e.g. "
            '{"type": "equals", "attribute": "status", "value": "Open"}. '
            "Group nodes: "
            '{"type": "and", "value": [node, node]}, '
            '{"type": "or", "value": [node, node]}, '
            '{"type": "not", "value": node}. '
            "Operators: equals, notEquals, isTrue, isFalse, isEmpty, "
            "isNotEmpty, contains, notContains, startsWith, endsWith, "
            "matches (regex), has, notHas, in, notIn, greaterThan, lessThan, "
            "greaterThanOrEquals, lessThanOrEquals, isToday, inFuture, inPast."
        )
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entity_type", "field_name", "action", "id"]
        verbose_name_plural = "dynamic logic rules"

    def __str__(self):
        return f"{self.entity_type}.{self.field_name} ({self.action})"

    def clean(self):
        super().clean()
        from omacrm.core.metadata.registry import registry
        from omacrm.core.services.dynamic_logic import condition_errors

        errors = {}
        if self.entity_type and not registry.has(self.entity_type):
            errors["entity_type"] = _("Unknown entity type.")
        elif self.entity_type:
            field_names = set(registry.fields(self.entity_type))
            field_names.update(registry.link_fields(self.entity_type))
            if self.field_name and self.field_name not in field_names:
                errors["field_name"] = _("Unknown field for this entity.")
        if not isinstance(self.condition, dict):
            errors["condition"] = _("Condition must be a JSON object.")
        else:
            problems = condition_errors(self.condition)
            if problems:
                errors["condition"] = " ".join(problems)
        if errors:
            raise ValidationError(errors)


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
        WEBHOOK = "webhook", _("Call webhook")
        UPDATE_RELATED = "update_related", _("Update related records")
        WAIT = "wait", _("Wait")
        BRANCH = "branch", _("Branch")

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
        from omacrm.core.services.workflows import validate_actions

        errors = {}
        if self.entity_type and not registry.has(self.entity_type):
            errors["entity_type"] = _("Unknown entity type.")
        elif self.entity_type:
            actions = self.actions or []
            if not isinstance(actions, list):
                errors["actions"] = _("Actions must be a list.")
            else:
                problem = validate_actions(actions, self.entity_type)
                if problem:
                    errors["actions"] = problem
        if errors:
            raise ValidationError(errors)


class WorkflowRun(models.Model):
    """One execution of a :class:`Workflow` rule.

    A run is persisted only when a rule reaches a ``wait`` step, so rules
    that execute entirely inline leave no rows behind. ``program`` is the
    compiled action list at creation time (see
    :mod:`omacrm.core.services.workflows`), which keeps in-flight runs stable
    when the rule is edited afterwards.
    """

    class Status(models.TextChoices):
        RUNNING = "running", _("Running")
        WAITING = "waiting", _("Waiting")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")

    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="runs"
    )
    entity_type = models.CharField(max_length=64, db_index=True)
    record_id = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    cursor = models.PositiveIntegerField(default=0)
    program = models.JSONField(default=list, blank=True)
    context = models.JSONField(default=dict, blank=True)
    execute_time = models.DateTimeField(null=True, blank=True, db_index=True)
    wait_deadline = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "workflow runs"

    def __str__(self):
        return f"{self.workflow} on {self.entity_type}#{self.record_id} ({self.status})"

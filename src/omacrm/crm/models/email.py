from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailTemplate(models.Model):
    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField(
        help_text=_(
            "Rendered HTML. Django template syntax is supported, e.g. {{ name }} "
            "or {{ record.name }}; the visual designer writes to this field."
        )
    )
    design = models.JSONField(
        null=True,
        blank=True,
        help_text=_("Visual designer project data (used to reopen the editor)."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

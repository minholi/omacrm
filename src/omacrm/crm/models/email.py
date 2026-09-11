from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailTemplate(models.Model):
    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField(
        help_text=_(
            "Django template syntax is supported, e.g. {{ name }} or {{ record.name }}."
        )
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

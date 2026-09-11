from django.db import models
from django.utils.translation import gettext_lazy as _

from omacrm.core.models import BaseEntity, CustomDataMixin


class KnowledgeBaseCategory(CustomDataMixin, models.Model):
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=100)
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Knowledge Base Category"
        verbose_name_plural = "Knowledge Base Categories"

    def __str__(self):
        return self.name


class KnowledgeBaseArticle(BaseEntity):
    class Status(models.TextChoices):
        DRAFT = "Draft", _("Draft")
        IN_REVIEW = "In Review", _("In Review")
        PUBLISHED = "Published", _("Published")
        ARCHIVED = "Archived", _("Archived")

    name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    language = models.CharField(max_length=10, blank=True, default="en")
    type = models.CharField(max_length=50, blank=True, default="Article")
    publish_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=100)
    description = models.TextField(blank=True, default="")
    body = models.TextField(blank=True, default="")
    body_plain = models.TextField(blank=True, default="", editable=False)
    categories = models.ManyToManyField(
        KnowledgeBaseCategory, blank=True, related_name="articles"
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Knowledge Base Article"
        verbose_name_plural = "Knowledge Base Articles"

    def __str__(self):
        return self.name

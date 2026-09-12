from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailTemplate(models.Model):
    SOURCE_FORMAT_CHOICES = [("mjml", "MJML"), ("html", "HTML")]

    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    source = models.TextField(
        blank=True,
        help_text=_(
            "Authored template code. Django template syntax is supported, e.g. "
            "{{ name }} or {{ record.name }}; MJML source is compiled to "
            "responsive HTML when the source format is MJML."
        ),
    )
    source_format = models.CharField(
        max_length=8,
        choices=SOURCE_FORMAT_CHOICES,
        default="html",
        help_text=_("Format of the authored source code."),
    )
    body = models.TextField(
        blank=True,
        default=(
            "Olá {{ name }}, escreva aqui a sua mensagem. Você pode usar "
            "{{ company_name }} e outras variáveis da lista de merge tags."
        ),
        help_text=_(
            "Compiled HTML. Django template syntax is supported, e.g. {{ name }} "
            "or {{ record.name }}; the visual designer writes to this field."
        ),
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

    def compile(self):
        """Compile ``source`` into ``body`` and return the compile result."""

        from omacrm.crm.services.email import compile_email_source

        result = compile_email_source(self.source or "", self.source_format)
        if result.html:
            self.body = result.html
        return result

    def clean(self):
        super().clean()
        if not (self.body or "").strip():
            raise ValidationError(
                {"body": [_("The template body cannot be empty.")]}
            )
        if not self.source:
            return

        from omacrm.crm.services.email import compile_email_source

        result = compile_email_source(self.source, self.source_format)
        if result.error:
            raise ValidationError({"source": [result.error, *result.warnings]})

    def save(self, *args, **kwargs):
        source_changed = bool(self.source) and (
            self.pk is None
            or EmailTemplate.objects.filter(pk=self.pk)
            .exclude(source=self.source)
            .exists()
        )
        if source_changed or (self.source and not self.body):
            self.compile()
        super().save(*args, **kwargs)

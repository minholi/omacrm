from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

STARTER_SOURCE = """<mjml>
  <mj-head>
    <mj-title>{{ company_name }}</mj-title>
    <mj-preview>News from {{ company_name }}</mj-preview>
    <mj-attributes>
      <mj-text font-family="Helvetica, Arial, sans-serif" font-size="15px" color="#374151" line-height="1.6" />
      <mj-button font-family="Helvetica, Arial, sans-serif" background-color="#4f46e5" color="#ffffff" border-radius="6px" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="#f3f4f6">
    <mj-section background-color="#ffffff" padding="24px">
      <mj-column>
        <mj-text align="center" font-size="20px" font-weight="bold" color="#111827">
          {{ company_name }}
        </mj-text>
      </mj-column>
    </mj-section>
    <mj-section background-color="#ffffff" padding="24px">
      <mj-column>
        <mj-text>Hello {{ name }},</mj-text>
        <mj-text>
          Start writing your message here. Replace this text with your content.
        </mj-text>
      </mj-column>
    </mj-section>
    <mj-raw>
      <div style="padding: 16px; text-align: center; font-size: 12px; color: #9ca3af;">
        &copy; {{ company_name }}. All rights reserved.
      </div>
    </mj-raw>
  </mj-body>
</mjml>
"""


class EmailTemplate(models.Model):
    SOURCE_FORMAT_CHOICES = [("mjml", "MJML"), ("html", "HTML")]

    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    source = models.TextField(
        blank=True,
        default=STARTER_SOURCE,
        help_text=_(
            "Authored template code and source of truth. Django template syntax "
            "is supported, e.g. {{ name }} or {{ record.name }}; MJML source is "
            "compiled to the responsive HTML stored in body."
        ),
    )
    source_format = models.CharField(
        max_length=8,
        choices=SOURCE_FORMAT_CHOICES,
        default="mjml",
        help_text=_("Format of the authored source code."),
    )
    body = models.TextField(
        blank=True,
        help_text=_("Compiled HTML cache derived from the source."),
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
        if not (self.source or "").strip():
            raise ValidationError(
                {"source": [_("The template source cannot be empty.")]}
            )

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

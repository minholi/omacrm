from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils.html import strip_tags

from omacrm.core.models import Note


def render_email_template(template, record):
    """Render an EmailTemplate against a record using Django templates."""

    fields = {}
    for field in record._meta.fields:
        fields[field.name] = getattr(record, field.attname, "")
    context = Context({"record": record, "object": record, **fields})

    subject = Template(template.subject).render(context)
    body = Template(template.body).render(context)
    return subject, body


def send_email(
    record,
    *,
    template=None,
    to_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    user=None,
):
    """Send an email related to a record and log it on the record stream."""

    to_email = to_email or getattr(record, "email_address", "") or ""
    if not to_email:
        raise ValueError("No recipient email address")

    if template is not None:
        rendered_subject, rendered_body = render_email_template(template, record)
        subject = subject or rendered_subject
        body = body or rendered_body

    if not subject:
        raise ValueError("Email subject is required")

    sent = send_mail(
        subject,
        strip_tags(body or ""),
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        html_message=body or None,
        fail_silently=False,
    )

    note = Note.objects.create(
        type=Note.Type.EMAIL,
        parent=record,
        post=subject,
        data={"to": to_email, "subject": subject},
        created_by=user,
    )
    return note, sent

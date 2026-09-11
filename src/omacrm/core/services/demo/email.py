"""Email demo data: templates, inbound threads and attachments."""

from omacrm.core.models import Attachment, Email
from omacrm.crm.models import EmailTemplate

from .common import moment_in, text_file

TEMPLATES = (
    (
        "Welcome",
        "Welcome, {{ name }}!",
        """
<style>
    .wrapper { background-color: #f3f4f6; padding: 24px; }
    .card { background-color: #ffffff; border-radius: 8px; padding: 24px;
            font-family: Arial, sans-serif; color: #1f2937; width: 600px; }
    .button { background-color: #4f46e5; border-radius: 6px; color: #ffffff;
              display: inline-block; padding: 10px 20px; text-decoration: none; }
    .muted { color: #6b7280; font-size: 12px; }
</style>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="wrapper">
    <tr>
        <td align="center">
            <table role="presentation" width="600" cellpadding="0" cellspacing="0" class="card">
                <tr>
                    <td>
                        <h1 style="margin: 0 0 12px 0;">Welcome, {{ name }}!</h1>
                        <p>Thank you for your interest in {{ company_name }}. Our team will
                           contact you shortly to understand how we can help.</p>
                        <p><a class="button" href="{{ record.email_address }}">Get in touch</a></p>
                        <p class="muted">{{ company_name }} &middot; This message was sent to
                           {{ email_address }}.</p>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
""",
    ),
    (
        "Follow-up",
        "Following up on {{ record.name }}",
        "<p>Hello {{ name }},</p><p>Just following up on our last conversation. Do you have 15 minutes this week?</p>",
    ),
    (
        "Newsletter",
        "OmaCRM monthly news",
        """
<style>
    .wrapper { background-color: #eef2ff; padding: 24px; }
    .card { background-color: #ffffff; border-radius: 8px; padding: 24px;
            font-family: Arial, sans-serif; color: #1f2937; width: 600px; }
    .heading { color: #4338ca; margin: 0 0 12px 0; }
    .item { border-top: 1px solid #e5e7eb; padding: 12px 0; }
    .muted { color: #6b7280; font-size: 12px; }
</style>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="wrapper">
    <tr>
        <td align="center">
            <table role="presentation" width="600" cellpadding="0" cellspacing="0" class="card">
                <tr>
                    <td>
                        <h1 class="heading">{{ company_name }} monthly news</h1>
                        <p>Hello {{ name }}, here is what is new this month.</p>
                        <div class="item"><strong>New reports</strong><br>
                            Dashboards now show campaign performance by channel.</div>
                        <div class="item"><strong>Faster search</strong><br>
                            Global search results now highlight matched fields.</div>
                        <p class="muted">You are receiving this email because you subscribed to
                           {{ company_name }} updates.</p>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
""",
    ),
    (
        "Case reply",
        "Update on your case {{ record.name }}",
        "<p>Hello {{ name }},</p><p>We have an update regarding your case. Reply to this message with any questions.</p>",
    ),
)


def _email(**kwargs):
    message_id = kwargs.pop("message_id")
    existing = Email.all_objects.filter(message_id=message_id).first()
    if existing is not None:
        return existing
    return Email.objects.create(message_id=message_id, **kwargs)


def seed_email(context):
    templates = {}
    for name, subject, body in TEMPLATES:
        template, _ = EmailTemplate.objects.get_or_create(
            name=name, defaults={"subject": subject, "body": body}
        )
        templates[name] = template

    john = context["contacts"]["john.carter@northwind.example"]
    mariana = context["contacts"]["mariana.silva@techbrasil.example"]
    northwind_deal = next(
        (item for item in context["opportunities"] if item.name == "Northwind ERP rollout"),
        None,
    )

    first = _email(
        subject="ERP rollout questions",
        body="Hi team, we have a few questions about the ERP rollout timeline.",
        body_plain="Hi team, we have a few questions about the ERP rollout timeline.",
        from_address="john.carter@northwind.example",
        to_address="support@example.com",
        message_id="<demo-thread-1@example.com>",
        thread_id="<demo-thread-1@example.com>",
        folder="INBOX",
        date_sent=moment_in(-5, 9),
        status=Email.Status.ARCHIVED,
        is_read=True,
        parent=john,
    )
    second = _email(
        subject="Re: ERP rollout questions",
        body="Hello John, attached is the timeline proposal we discussed.",
        body_plain="Hello John, attached is the timeline proposal we discussed.",
        from_address="support@example.com",
        to_address="john.carter@northwind.example",
        message_id="<demo-thread-2@example.com>",
        thread_id="<demo-thread-1@example.com>",
        parent_email=first,
        folder="Sent",
        date_sent=moment_in(-5, 11),
        status=Email.Status.SENT,
        is_read=True,
        parent=northwind_deal or john,
    )
    third = _email(
        subject="Re: ERP rollout questions",
        body="Thanks! Two notes on milestones and billing.",
        body_plain="Thanks! Two notes on milestones and billing.",
        from_address="john.carter@northwind.example",
        to_address="support@example.com",
        message_id="<demo-thread-3@example.com>",
        thread_id="<demo-thread-1@example.com>",
        parent_email=second,
        folder="INBOX",
        date_sent=moment_in(-4, 8),
        status=Email.Status.ARCHIVED,
        is_read=False,
        parent=northwind_deal or john,
    )
    from django.contrib.contenttypes.models import ContentType

    email_ct = ContentType.objects.get_for_model(third, for_concrete_model=False)
    if not Attachment.objects.filter(
        related_type=email_ct, related_id=third.pk
    ).exists():
        for index, filename in enumerate(("milestones.txt", "billing-notes.txt"), start=1):
            Attachment(
                name=filename,
                mime_type="text/plain",
                file=text_file(
                    filename,
                    f"Attachment {index} for the ERP rollout thread.\n",
                ),
                related=third,
            ).save()

    _email(
        subject="Cloud migration kickoff",
        body="Hello Mariana, let us schedule the kickoff for next week.",
        body_plain="Hello Mariana, let us schedule the kickoff for next week.",
        from_address="mariana.silva@techbrasil.example",
        to_address="support@example.com",
        message_id="<demo-thread-2a@example.com>",
        thread_id="<demo-thread-2a@example.com>",
        folder="INBOX",
        date_sent=moment_in(-2, 14),
        status=Email.Status.ARCHIVED,
        is_read=False,
        parent=mariana,
    )

    context.update({"email_templates": templates})

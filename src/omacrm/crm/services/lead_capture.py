"""Shared logic for public lead capture (JSON API and hosted form)."""

import logging

from django import forms
from django.conf import settings as django_settings
from django.core import signing
from django.core.exceptions import FieldDoesNotExist
from django.core.mail import send_mail
from django.db import models as django_models
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from omacrm.crm.models import CampaignLogRecord, Lead, LeadCapture
from omacrm.crm.services.target_lists import add_to_target_list

logger = logging.getLogger(__name__)

DEFAULT_CAPTURE_FIELDS = [
    "first_name",
    "last_name",
    "email_address",
    "phone_number",
    "description",
]

CAPTCHA_TOKEN_FIELDS = (
    "captcha_token",
    "g-recaptcha-response",
    "cf-turnstile-response",
)

CAPTCHA_ERROR_MESSAGES = {
    "not_configured": _("The form is temporarily unavailable. Please try again later."),
    "missing": _("Please complete the captcha."),
    "failed": _("The captcha verification failed. Please try again."),
}

LEAD_CAPTURE_OPT_IN_SALT = "omacrm.lead_capture.opt_in"


def form_fields(capture: LeadCapture) -> list[str]:
    """Renderable Lead fields allowed by the capture, in configured order."""

    allowed = capture.field_list or DEFAULT_CAPTURE_FIELDS
    renderable = (django_models.TextField, django_models.CharField)
    result = []
    for name in allowed:
        try:
            field = Lead._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if isinstance(field, renderable):
            result.append(name)
    return result


class LeadCaptureForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("last_name") and not cleaned.get("email_address"):
            raise forms.ValidationError(
                _("Please provide a last name or an email address.")
            )
        return cleaned


def build_form(capture: LeadCapture, data=None) -> forms.ModelForm:
    """A Lead ModelForm bound to the capture's allowed web-form fields."""

    form_class = forms.modelform_factory(
        Lead, form=LeadCaptureForm, fields=form_fields(capture)
    )
    return form_class(data=data)


def captcha_error(capture: LeadCapture, token: str, request) -> str:
    """Return ``""`` when the submission may proceed, else an error code."""

    if not capture.form_captcha:
        return ""

    from omacrm.core.services import captcha

    if not captcha.is_configured():
        logger.error(
            "Lead capture %s requires a captcha but no provider is configured",
            capture.pk,
        )
        return "not_configured"
    if not token:
        return "missing"
    if not captcha.verify(
        token, "lead_capture", remote_ip=request.META.get("REMOTE_ADDR")
    ):
        return "failed"
    return ""


def captcha_token(data) -> str:
    for field in CAPTCHA_TOKEN_FIELDS:
        value = data.get(field)
        if value:
            return str(value)
    return ""


def captcha_config(capture: LeadCapture) -> dict:
    """Provider and site key to embed on the hosted form."""

    if not capture.form_captcha:
        return {"provider": "", "site_key": ""}

    from omacrm.core.services import captcha

    return {"provider": captcha.provider(), "site_key": captcha.site_key()}


def store_lead(capture: LeadCapture, values: dict, request) -> tuple[Lead, bool]:
    """Create the lead and run the capture's side effects.

    Returns the lead and whether the double opt-in confirmation is pending.
    """

    lead = Lead(**values)
    lead.source = capture.source
    if capture.default_assigned_user_id:
        lead.assigned_user = capture.default_assigned_user
    lead.save()

    if capture.campaign_id:
        CampaignLogRecord.objects.create(
            campaign=capture.campaign,
            action=CampaignLogRecord.Action.LEAD_CREATED,
            entity=lead,
            data={"email": lead.email_address},
        )

    if capture.opt_in_confirmation:
        send_opt_in_confirmation(request, lead, capture)
        return lead, True

    if capture.target_list_id:
        add_to_target_list(lead, capture.target_list)
    return lead, False


def send_opt_in_confirmation(request, lead: Lead, capture: LeadCapture) -> None:
    from omacrm.crm.services.email import render_email_template

    token = signing.dumps(
        {"lead": lead.pk, "capture": capture.pk}, salt=LEAD_CAPTURE_OPT_IN_SALT
    )
    url = request.build_absolute_uri(reverse("lead_capture_confirm", args=[token]))

    if capture.opt_in_template_id:
        subject, body = render_email_template(capture.opt_in_template, lead)
    else:
        subject, body = (
            _("Please confirm your subscription"),
            f"<p>{_('Confirm your subscription:')}</p>",
        )

    body = f'{body}\n<p><a href="{url}">{url}</a></p>'
    send_mail(
        subject,
        strip_tags(body),
        django_settings.DEFAULT_FROM_EMAIL,
        [lead.email_address],
        html_message=body,
        fail_silently=True,
    )


def company_name() -> str:
    try:
        from constance import config

        return config.company_name or "OmaCRM"
    except Exception:  # noqa: BLE001 - constance may be unavailable
        return "OmaCRM"

import base64
import json

from django.conf import settings as django_settings
from django.core import signing
from django.core.mail import send_mail
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from omacrm.crm.models import (
    Campaign,
    CampaignLogRecord,
    CampaignTrackingUrl,
    Lead,
    LeadCapture,
)
from omacrm.crm.services.event_invitations import confirm_attendance
from omacrm.crm.services.target_lists import add_to_target_list

PIXEL_GIF = base64.b64decode(
    b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

DEFAULT_CAPTURE_FIELDS = [
    "first_name",
    "last_name",
    "email_address",
    "phone_number",
    "description",
]

LEAD_CAPTURE_OPT_IN_SALT = "omacrm.lead_capture.opt_in"


def campaign_track_click(request, pk):
    tracking = get_object_or_404(CampaignTrackingUrl, pk=pk)

    CampaignLogRecord.objects.create(
        campaign=tracking.campaign,
        action=CampaignLogRecord.Action.CLICKED,
        data={"url": tracking.url},
    )
    Campaign.objects.filter(pk=tracking.campaign_id).update(
        clicked_count=F("clicked_count") + 1
    )

    if tracking.action == CampaignTrackingUrl.Action.SHOW_MESSAGE:
        return render(
            request,
            "crm/campaign_message.html",
            {
                "title": tracking.name,
                "message": tracking.message or _("Thank you."),
            },
        )
    return HttpResponseRedirect(tracking.url or "/")


def campaign_track_open(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    CampaignLogRecord.objects.create(
        campaign=campaign, action=CampaignLogRecord.Action.OPENED
    )
    Campaign.objects.filter(pk=pk).update(opened_count=F("opened_count") + 1)
    return HttpResponse(PIXEL_GIF, content_type="image/gif")


@csrf_exempt
@require_POST
def lead_capture(request, api_key):
    capture = LeadCapture.objects.filter(api_key=api_key, is_active=True).first()
    if capture is None:
        return JsonResponse({"error": "invalid api key"}, status=404)

    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid json"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "invalid payload"}, status=400)

    allowed = capture.field_list or DEFAULT_CAPTURE_FIELDS
    values = {key: value for key, value in data.items() if key in allowed}
    if not values.get("last_name") and not values.get("email_address"):
        return JsonResponse(
            {"error": "last_name or email_address is required"}, status=400
        )

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
        _send_opt_in_confirmation(request, lead, capture)
        return JsonResponse(
            {"id": lead.pk, "status": "pending_confirmation"}, status=201
        )

    if capture.target_list_id:
        add_to_target_list(lead, capture.target_list)

    return JsonResponse({"id": lead.pk}, status=201)


def _send_opt_in_confirmation(request, lead: Lead, capture: LeadCapture) -> None:
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


def lead_capture_confirm(request, token):
    """Public double opt-in confirmation for lead capture."""

    try:
        data = signing.loads(
            token,
            salt=LEAD_CAPTURE_OPT_IN_SALT,
        )
    except signing.BadSignature:
        return HttpResponseBadRequest(
            _("This confirmation link is invalid or has expired.")
        )

    lead = Lead.objects.filter(pk=data.get("lead")).first()
    capture = LeadCapture.objects.filter(pk=data.get("capture")).first()
    if lead is None or capture is None:
        return HttpResponseBadRequest(_("This confirmation link is invalid."))

    if not lead.opt_in_confirmed:
        lead.opt_in_confirmed = True
        lead.opt_in_confirmed_at = timezone.now()
        lead.save(update_fields=["opt_in_confirmed", "opt_in_confirmed_at"])
        if capture.target_list_id:
            add_to_target_list(lead, capture.target_list)

    return render(
        request,
        "crm/lead_capture_confirmed.html",
        {"lead": lead, "capture": capture},
    )


def mass_email_unsubscribe(request, token):
    """Public opt-out link included in mass emails."""

    from omacrm.crm.models import EmailQueueItem
    from omacrm.crm.services.mass_email import UNSUBSCRIBE_SALT, unsubscribe

    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return HttpResponseBadRequest(_("This unsubscribe link is invalid."))

    queue_item = EmailQueueItem.objects.filter(pk=data.get("id")).first()
    if queue_item is None:
        return HttpResponseBadRequest(_("This unsubscribe link is invalid."))

    unsubscribe(queue_item)
    return render(
        request,
        "crm/unsubscribed.html",
        {"email": queue_item.email_address},
    )


def event_confirmation(request, pk, action, token):
    """Public accept/decline page for event invitations."""

    attendance = confirm_attendance(pk, action, token)
    if attendance is None:
        return HttpResponseBadRequest(
            _("This invitation link is invalid or has expired.")
        )
    return render(
        request,
        "crm/event_confirmation.html",
        {
            "attendance": attendance,
            "event": attendance.event,
            "accepted": action == "accept",
        },
    )

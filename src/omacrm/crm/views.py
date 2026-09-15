import base64
import json

from django.core import signing
from django.db.models import F
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
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
from omacrm.crm.services import lead_capture as lead_capture_service
from omacrm.crm.services.event_invitations import confirm_attendance
from omacrm.crm.services.target_lists import add_to_target_list

PIXEL_GIF = base64.b64decode(
    b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


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

    allowed = capture.field_list or lead_capture_service.DEFAULT_CAPTURE_FIELDS
    values = {key: value for key, value in data.items() if key in allowed}
    if not values.get("last_name") and not values.get("email_address"):
        return JsonResponse(
            {"error": "last_name or email_address is required"}, status=400
        )

    error = lead_capture_service.captcha_error(
        capture, lead_capture_service.captcha_token(data), request
    )
    if error == "not_configured":
        return JsonResponse({"error": "captcha is not configured"}, status=503)
    if error == "missing":
        return JsonResponse({"error": "captcha token required"}, status=400)
    if error == "failed":
        return JsonResponse({"error": "captcha verification failed"}, status=403)

    lead, pending = lead_capture_service.store_lead(capture, values, request)
    if pending:
        return JsonResponse(
            {"id": lead.pk, "status": "pending_confirmation"}, status=201
        )
    return JsonResponse({"id": lead.pk}, status=201)


def lead_capture_form(request, api_key):
    """Hosted web-to-lead form for one capture."""

    capture = LeadCapture.objects.filter(api_key=api_key, is_active=True).first()
    if capture is None:
        raise Http404("Unknown lead capture form.")

    form = lead_capture_service.build_form(
        capture, data=request.POST if request.method == "POST" else None
    )

    captcha_error = ""
    if request.method == "POST":
        captcha_error = lead_capture_service.captcha_error(
            capture, lead_capture_service.captcha_token(request.POST), request
        )
        if not captcha_error and form.is_valid():
            lead, pending = lead_capture_service.store_lead(
                capture, form.cleaned_data, request
            )
            return render(
                request,
                "crm/lead_capture_form_done.html",
                {
                    "capture": capture,
                    "lead": lead,
                    "pending": pending,
                    "company_name": lead_capture_service.company_name(),
                },
            )

    return render(
        request,
        "crm/lead_capture_form.html",
        {
            "capture": capture,
            "form": form,
            "captcha": lead_capture_service.captcha_config(capture),
            "captcha_error": lead_capture_service.CAPTCHA_ERROR_MESSAGES.get(
                captcha_error, ""
            ),
            "company_name": lead_capture_service.company_name(),
        },
    )


def lead_capture_confirm(request, token):
    """Public double opt-in confirmation for lead capture."""

    try:
        data = signing.loads(
            token,
            salt=lead_capture_service.LEAD_CAPTURE_OPT_IN_SALT,
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

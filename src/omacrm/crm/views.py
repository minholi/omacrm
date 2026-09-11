import base64
import json

from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
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

    if capture.target_list_id:
        add_to_target_list(lead, capture.target_list)

    return JsonResponse({"id": lead.pk}, status=201)

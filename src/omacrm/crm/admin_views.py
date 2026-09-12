"""Admin views for the visual email template designer (GrapesJS)."""

import json
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from PIL import Image, UnidentifiedImageError

from omacrm.crm.models import Account, Contact, EmailTemplate, Lead
from omacrm.crm.services.email import (
    MERGE_TAGS,
    looks_like_html,
    prepare_email_html,
    render_email_template,
    send_email,
)

CHANGE_PERMISSION = "crm.change_emailtemplate"
MAX_DESIGN_BYTES = 4 * 1024 * 1024
MAX_ASSET_BYTES = 5 * 1024 * 1024
ASSET_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

PREVIEW_MODELS = {
    "Contact": Contact,
    "Account": Account,
    "Lead": Lead,
}


def _check_change_permission(request):
    if not request.user.has_perm(CHANGE_PERMISSION):
        raise PermissionDenied


def _get_template(pk):
    return get_object_or_404(EmailTemplate, pk=pk)


def _preview_record(request):
    data = request.POST if request.method == "POST" else request.GET
    entity = data.get("entity") or ""
    pk = data.get("pk") or ""
    model = PREVIEW_MODELS.get(entity)
    if model is not None and pk:
        record = model.objects.filter(pk=pk).first()
        if record is not None:
            return record

    for candidate in PREVIEW_MODELS.values():
        record = candidate.objects.order_by("pk").first()
        if record is not None:
            return record

    return Contact(
        first_name="Jane",
        last_name="Doe",
        email_address="jane.doe@example.com",
        phone_number="+15550100",
    )


class EmailTemplateDesignView(TemplateView):
    template_name = "admin/crm/email_template_design.html"

    def get_context_data(self, **kwargs):
        _check_change_permission(self.request)
        email_template = _get_template(kwargs["pk"])
        context = super().get_context_data(**kwargs)
        context["title"] = _("Design: %(name)s") % {"name": email_template.name}
        context["email_template"] = email_template
        context["designer_config"] = {
            "name": email_template.name,
            "body": email_template.body or "",
            "design": email_template.design,
            "mergeTags": MERGE_TAGS,
            "saveUrl": reverse("email_template_design_save", args=[email_template.pk]),
            "previewUrl": reverse("email_template_preview", args=[email_template.pk]),
            "testSendUrl": reverse(
                "email_template_test_send", args=[email_template.pk]
            ),
            "assetUploadUrl": reverse("email_asset_upload"),
            "backUrl": reverse(
                "admin:crm_emailtemplate_change", args=[email_template.pk]
            ),
            "csrfToken": get_token(self.request),
            "labels": {
                "saving": _("Saving..."),
                "saved": _("Saved"),
                "error": _("Error: %(error)s"),
                "sendingTest": _("Sending..."),
                "testPrompt": _("Send a test email to:"),
                "testSent": _("Test email sent to %(to)s"),
            },
        }
        return context


@require_POST
def email_template_design_save(request, pk):
    _check_change_permission(request)
    email_template = _get_template(pk)

    if len(request.body or b"") > MAX_DESIGN_BYTES:
        return JsonResponse(
            {"ok": False, "error": _("The design is too large to save.")}, status=400
        )
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": _("Invalid JSON payload.")}, status=400
        )
    if not isinstance(payload, dict):
        return JsonResponse(
            {"ok": False, "error": _("Invalid JSON payload.")}, status=400
        )

    html = str(payload.get("html") or "")
    css = str(payload.get("css") or "")
    design = payload.get("design")
    if design is not None and not isinstance(design, (dict, list)):
        return JsonResponse(
            {"ok": False, "error": _("Invalid design data.")}, status=400
        )
    if not html.strip():
        return JsonResponse(
            {"ok": False, "error": _("The template body cannot be empty.")}, status=400
        )

    raw = f"<style>{css}</style>{html}" if css.strip() else html
    body, _text = prepare_email_html(raw)

    email_template.body = body
    email_template.source = body
    email_template.source_format = "html"
    email_template.design = design
    email_template.save(
        update_fields=["body", "source", "source_format", "design", "modified_at"]
    )
    return JsonResponse({"ok": True})


def email_template_preview(request, pk):
    _check_change_permission(request)
    email_template = _get_template(pk)
    _subject, body = render_email_template(email_template, _preview_record(request))
    if not looks_like_html(body):
        body = f'<pre style="white-space:pre-wrap">{escape(body)}</pre>'
    html_body, _text = prepare_email_html(body)
    return HttpResponse(html_body, content_type="text/html")


@require_POST
def email_template_test_send(request, pk):
    _check_change_permission(request)
    email_template = _get_template(pk)
    to_email = (request.POST.get("to_email") or request.user.email or "").strip()
    if not to_email:
        return JsonResponse(
            {"ok": False, "error": _("Provide a recipient email address.")},
            status=400,
        )

    record = _preview_record(request)
    if getattr(record, "pk", None) is None:
        return JsonResponse(
            {
                "ok": False,
                "error": _(
                    "No record is available for the test send. Create a Contact first."
                ),
            },
            status=400,
        )

    try:
        send_email(
            record, template=email_template, to_email=to_email, user=request.user
        )
    except Exception as exc:  # noqa: BLE001 - surface delivery errors in the editor
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "to": to_email})


@require_POST
def email_asset_upload(request):
    _check_change_permission(request)
    uploads = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not uploads:
        return JsonResponse(
            {"error": _("No files were uploaded.")}, status=400
        )

    data = []
    for upload in uploads:
        extension = Path(upload.name or "").suffix.lower()
        if extension not in ASSET_EXTENSIONS or not (
            upload.content_type or ""
        ).startswith("image/"):
            return JsonResponse(
                {"error": _("Only image files are allowed.")}, status=400
            )
        if upload.size > MAX_ASSET_BYTES:
            return JsonResponse(
                {"error": _("Images must be 5 MB or smaller.")}, status=400
            )
        try:
            Image.open(upload).verify()
        except (UnidentifiedImageError, OSError):
            return JsonResponse(
                {"error": _("The file is not a valid image.")}, status=400
            )
        upload.seek(0)

        stored_name = f"email-assets/{uuid4().hex}{extension}"
        saved_name = default_storage.save(stored_name, File(upload))
        data.append(
            {
                "src": default_storage.url(saved_name),
                "name": upload.name,
                "type": "image",
            }
        )

    return JsonResponse({"data": data})

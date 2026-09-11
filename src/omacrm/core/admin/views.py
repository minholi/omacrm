import calendar
import json
import time
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import admin, messages
from django.db.models import Q
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from omacrm.core.metadata.registry import registry
from omacrm.core.models import Layout
from omacrm.core.services.acl import AclService

WEEKDAYS = [
    _("Mon"),
    _("Tue"),
    _("Wed"),
    _("Thu"),
    _("Fri"),
    _("Sat"),
    _("Sun"),
]

EVENT_TYPES = [
    ("Call", "info", "call"),
    ("Meeting", "primary", "event"),
    ("Task", "warning", "task_alt"),
]


class CalendarView(TemplateView):
    template_name = "admin/crm/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))

        today = timezone.localdate()
        try:
            year = int(self.request.GET.get("year", today.year))
            month = int(self.request.GET.get("month", today.month))
            if not 1 <= month <= 12 or not 1900 <= year <= 2200:
                raise ValueError
        except (TypeError, ValueError):
            year, month = today.year, today.month

        assigned = self.request.GET.get("assigned", "me")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        events = self._collect_events(first_day, last_day, assigned)

        events_by_date = defaultdict(list)
        for event in events:
            events_by_date[event["date"]].append(event)

        today_date = timezone.localdate()
        weeks = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
            days = []
            for day in week:
                days.append(
                    {
                        "date": day,
                        "in_month": day.month == month,
                        "today": day == today_date,
                        "events": events_by_date.get(day, []),
                    }
                )
            weeks.append(days)

        previous_month = first_day - timedelta(days=1)
        next_month = last_day + timedelta(days=1)

        context.update(
            {
                "title": _("Calendar"),
                "weeks": weeks,
                "weekdays": WEEKDAYS,
                "month_label": first_day.strftime("%B %Y"),
                "prev_year": previous_month.year,
                "prev_month": previous_month.month,
                "next_year": next_month.year,
                "next_month": next_month.month,
                "year": year,
                "month": month,
                "assigned": assigned,
                "today": today,
                "agenda": events[:100],
            }
        )
        return context

    def _collect_events(self, first_day: date, last_day: date, assigned: str):
        from omacrm.crm.models import Call, Meeting, Task

        models = {"Call": Call, "Meeting": Meeting, "Task": Task}
        events = []

        for entity_type, variant, icon in EVENT_TYPES:
            model = models[entity_type]
            queryset = model.objects.filter(
                Q(date_start__date__gte=first_day, date_start__date__lte=last_day)
                | Q(date_end__date__gte=first_day, date_end__date__lte=last_day)
            )
            if assigned == "me":
                queryset = queryset.filter(assigned_user=self.request.user)
            queryset = AclService.scope_queryset(
                self.request.user, entity_type, queryset, "read"
            )

            for obj in queryset.select_related("assigned_user"):
                moment = obj.date_start or obj.date_end
                if moment is None:
                    continue
                local_moment = timezone.localtime(moment)
                events.append(
                    {
                        "type": entity_type,
                        "name": str(obj),
                        "when": local_moment,
                        "date": local_moment.date(),
                        "url": reverse(
                            f"admin:crm_{model._meta.model_name}_change", args=[obj.pk]
                        ),
                        "variant": variant,
                        "icon": icon,
                        "status": obj.status,
                        "assigned": obj.assigned_user.name if obj.assigned_user else "",
                    }
                )

        events.sort(key=lambda event: event["when"])
        return events


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class LayoutEditorIndexView(TemplateView):
    template_name = "admin/layout_editor_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        context["title"] = _("Layout Editor")

        rows = []
        for entity_type in registry.entity_types():
            entity = registry.get(entity_type)
            custom_list = Layout.objects.filter(
                entity_type=entity_type, layout_name="list"
            ).exists()
            custom_detail = Layout.objects.filter(
                entity_type=entity_type, layout_name="detail"
            ).exists()
            rows.append(
                {
                    "entity_type": entity_type,
                    "label": entity.display_label,
                    "field_count": len(registry.fields(entity_type)),
                    "custom_list": custom_list,
                    "custom_detail": custom_detail,
                    "url": reverse("layout_editor", kwargs={"entity_type": entity_type}),
                }
            )
        context["entities"] = rows
        return context


class LayoutEditorView(TemplateView):
    template_name = "admin/layout_editor_form.html"

    def get_context_data(self, **kwargs):
        import json

        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        entity_type = kwargs["entity_type"]
        if not registry.has(entity_type):
            raise Http404(f"Unknown entity type: {entity_type}")
        entity = registry.get(entity_type)
        context["title"] = _("Layout Editor: %(entity)s") % {"entity": entity.display_label}
        context["entity_type"] = entity_type
        context["entity"] = entity
        context["fields"] = list(registry.fields(entity_type).values())

        layout_record = Layout.objects.filter(
            entity_type=entity_type, layout_name="list"
        ).first()
        context["list_layout"] = (
            layout_record.data
            if layout_record is not None
            else list(entity.list_layout)
        )

        detail = registry.layout(entity_type, "detail") or []
        context["detail_layout_text"] = json.dumps(_jsonable(detail), indent=2)
        return context

    def post(self, request, *args, **kwargs):
        import json

        from django.contrib import messages
        from django.shortcuts import redirect

        entity_type = kwargs["entity_type"]
        if not registry.has(entity_type):
            raise Http404(f"Unknown entity type: {entity_type}")
        entity = registry.get(entity_type)
        fields = registry.fields(entity_type)

        list_fields = [name for name in request.POST.getlist("list_fields") if name in fields]

        raw_layout = request.POST.get("detail_layout", "").strip()
        try:
            sections = json.loads(raw_layout) if raw_layout else []
        except ValueError as exc:
            messages.error(request, _("Invalid JSON: %(error)s") % {"error": exc})
            return redirect("layout_editor", entity_type=entity_type)

        if not isinstance(sections, list):
            messages.error(request, _("The detail layout must be a JSON list."))
            return redirect("layout_editor", entity_type=entity_type)

        cleaned = []
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get("fields", []), list):
                messages.error(
                    request,
                    _("Each section must be an object with a 'fields' list."),
                )
                return redirect("layout_editor", entity_type=entity_type)
            unknown = [name for name in section.get("fields", []) if name not in fields]
            if unknown:
                messages.error(
                    request,
                    _("Unknown field(s): %(fields)s") % {"fields": ", ".join(unknown)},
                )
                return redirect("layout_editor", entity_type=entity_type)
            cleaned.append(
                {"title": section.get("title"), "fields": list(section.get("fields", []))}
            )

        Layout.objects.update_or_create(
            entity_type=entity_type,
            layout_name="list",
            defaults={"data": list_fields, "is_custom": True},
        )
        Layout.objects.update_or_create(
            entity_type=entity_type,
            layout_name="detail",
            defaults={"data": cleaned, "is_custom": True},
        )
        messages.success(request, _("Layout updated."))
        return redirect("layout_editor", entity_type=entity_type)


class RoleAclEditorView(TemplateView):
    template_name = "admin/role_acl_editor.html"

    ACTIONS = ["read", "create", "edit", "delete"]
    LEVELS = ["", "yes", "all", "team", "own", "no"]

    def get_context_data(self, **kwargs):
        from django.shortcuts import get_object_or_404

        from omacrm.core.models import Role

        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        role = get_object_or_404(Role, pk=kwargs["pk"])
        context["title"] = _("Access Matrix: %(role)s") % {"role": role.name}
        context["role"] = role
        context["actions"] = self.ACTIONS
        context["levels"] = self.LEVELS

        rows = []
        for entity_type in registry.entity_types():
            scope = (role.data or {}).get(entity_type, {})
            rows.append(
                {
                    "entity_type": entity_type,
                    "label": registry.get(entity_type).display_label,
                    "levels": {action: scope.get(action, "") for action in self.ACTIONS},
                }
            )
        context["entity_rows"] = rows

        entity_types = registry.entity_types()
        selected = self.request.GET.get("entity") or (entity_types[0] if entity_types else "")
        context["selected_entity"] = selected
        field_rows = []
        if selected and registry.has(selected):
            field_data = (role.field_data or {}).get(selected, {})
            field_rows = [
                {
                    "name": name,
                    "type": field_def.type,
                    "level": field_data.get(name, ""),
                }
                for name, field_def in registry.fields(selected).items()
            ]
        context["field_rows"] = field_rows
        return context

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        from django.shortcuts import get_object_or_404, redirect

        from omacrm.core.models import Role

        role = get_object_or_404(Role, pk=kwargs["pk"])

        data = {}
        for key, value in request.POST.items():
            if key.startswith("scope__") and value:
                _prefix, entity_type, action = key.split("__", 2)
                data.setdefault(entity_type, {})[action] = value

        field_data = {
            entity: dict(levels) for entity, levels in (role.field_data or {}).items()
        }
        selected = request.POST.get("selected_entity")
        if selected:
            collected = {}
            prefix = f"field__{selected}__"
            for key, value in request.POST.items():
                if key.startswith(prefix) and value:
                    collected[key[len(prefix):]] = value
            if collected:
                field_data[selected] = collected
            else:
                field_data.pop(selected, None)

        role.data = data
        role.field_data = field_data
        role.save(update_fields=["data", "field_data"])
        messages.success(request, _("Access matrix updated."))

        url = reverse("role_acl_editor", args=[role.pk])
        if selected:
            url = f"{url}?entity={selected}"
        return redirect(url)


def notification_stream(request):
    """Server-sent events with the user's notification count and new items."""

    from omacrm.core.models import Notification

    user = request.user

    def unread_count():
        return Notification.objects.filter(user=user, read=False).count()

    def events():
        last_id = (
            Notification.objects.filter(user=user)
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
            or 0
        )
        yield f"data: {json.dumps({'type': 'init', 'count': unread_count()})}\n\n"

        # Each connection lives ~5 minutes, then EventSource reconnects.
        for _ in range(100):
            time.sleep(3)
            new_items = list(
                Notification.objects.filter(user=user, id__gt=last_id, read=False)
                .order_by("id")
                .values("id", "message", "type")[:10]
            )
            if not new_items:
                yield ": ping\n\n"
                continue
            last_id = new_items[-1]["id"]
            for item in new_items:
                yield "data: " + json.dumps(
                    {
                        "type": "new",
                        "count": unread_count(),
                        "id": item["id"],
                        "message": item["message"],
                        "category": item["type"],
                    }
                ) + "\n\n"

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


class MassUpdateView(TemplateView):
    """Intermediate page that applies one value to many selected records."""

    template_name = "admin/mass_update.html"

    @property
    def model_admin(self):
        return self.kwargs.get("model_admin")

    def _changelist_url(self):
        meta = self.model_admin.model._meta
        return reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")

    def _mass_update_url(self, token):
        return f"{reverse(f'admin:{self.model_admin.mass_update_url_name()}')}?token={token}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        context["title"] = _("Mass update: %(model)s") % {
            "model": self.model_admin.model._meta.verbose_name_plural
        }
        context["model_admin"] = self.model_admin
        context["changelist_url"] = self._changelist_url()

        token = self.request.GET.get("token") or self.request.POST.get("token") or ""
        context["token"] = token
        session_data = self.request.session.get(f"mass_update:{token}") or {}
        context["count"] = len(session_data.get("pks", []))
        context["fields"] = self.model_admin.mass_update_fields()
        return context

    def post(self, request, *args, **kwargs):
        model_admin = self.model_admin
        token = request.POST.get("token") or ""
        session_data = request.session.get(f"mass_update:{token}")

        if not session_data:
            messages.error(
                request,
                _("The selection expired. Please select the records again."),
            )
            return redirect(self._changelist_url())

        definition = (request.POST.get("definition") or "").strip()
        field_name, _separator, raw_value = definition.partition(":")
        fields_by_name = {field["name"]: field for field in model_admin.mass_update_fields()}
        field = fields_by_name.get(field_name)

        valid_value = field is not None and any(
            str(value) == raw_value for value, _label in field["choices"]
        )
        if not valid_value:
            messages.error(request, _("Invalid mass update value."))
            return redirect(self._mass_update_url(token))

        pks = session_data.get("pks", [])
        updated = 0
        queryset = model_admin.model.objects.filter(pk__in=pks)
        for obj in queryset:
            if not AclService.check(request.user, model_admin.entity_type, "edit", obj):
                continue

            if field_name == "assigned_user":
                obj.assigned_user_id = int(raw_value) if raw_value else None
            else:
                field_def = registry.field(model_admin.entity_type, field_name)
                value = (
                    raw_value == "True"
                    if field_def and field_def.type == "bool"
                    else raw_value
                )
                setattr(obj, field_name, value)
            # A full save lets before-save hooks (e.g. date_completed) persist.
            obj.save()
            updated += 1

        del request.session[f"mass_update:{token}"]
        messages.success(
            request,
            _("%(count)s record(s) updated.") % {"count": updated},
        )
        return redirect(self._changelist_url())

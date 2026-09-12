import calendar
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
from unfold.views import BaseAutocompleteView, UnfoldSiteViewMixin

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


class CalendarView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = _("Calendar")

    template_name = "admin/crm/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

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

        from urllib.parse import urlencode

        def month_url(day, assigned_value):
            query = urlencode(
                {"year": day.year, "month": day.month, "assigned": assigned_value}
            )
            return f"{reverse('crm_calendar')}?{query}"

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
                "prev_url": month_url(previous_month, assigned),
                "today_url": month_url(today, assigned),
                "next_url": month_url(next_month, assigned),
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

        events.extend(self._collect_dynamic_events(first_day, last_day, assigned))
        events.sort(key=lambda event: event["when"])
        return events

    def _collect_dynamic_events(self, first_day: date, last_day: date, assigned: str):
        """Calendar records of custom entities flagged with ``show_in_calendar``."""

        events = []
        for entity_type in registry.entity_types():
            entity = registry.get(entity_type)
            if not entity.dynamic or not entity.calendar:
                continue
            model = registry.model_for(entity_type)
            queryset = model.objects.filter(entity_type=entity_type)
            if assigned == "me":
                queryset = queryset.filter(assigned_user=self.request.user)
            queryset = AclService.scope_queryset(
                self.request.user, entity_type, queryset, "read"
            )
            meta = model._meta
            for obj in queryset.select_related("assigned_user"):
                data = obj.custom_data or {}
                start = _parse_json_moment(data.get("date_start"))
                end = _parse_json_moment(data.get("date_end"))
                moment = start or end
                if moment is None or not (first_day <= moment.date() <= last_day):
                    continue
                events.append(
                    {
                        "type": entity_type,
                        "name": str(obj),
                        "when": moment,
                        "date": moment.date(),
                        "url": reverse(
                            f"admin:{meta.app_label}_{meta.model_name}_change",
                            args=[obj.pk],
                        ),
                        "variant": "success",
                        "icon": entity.icon or "event",
                        "status": data.get("status", ""),
                        "assigned": obj.assigned_user.name if obj.assigned_user else "",
                    }
                )
        return events


class LinkAutocompleteView(BaseAutocompleteView):
    """Select2 JSON results for custom link pickers (ACL-scoped)."""

    paginate_by = 20

    def get_queryset(self):
        entity_type = self.request.GET.get("entity_type", "")
        if not registry.has(entity_type):
            raise Http404("Unknown entity type.")
        if not AclService.check(self.request.user, entity_type, "read"):
            raise PermissionDenied("You cannot read this entity.")

        model = registry.model_for(entity_type)
        queryset = model.objects.all()
        if registry.is_dynamic(entity_type):
            queryset = queryset.filter(entity_type=entity_type)
        queryset = AclService.scope_queryset(
            self.request.user, entity_type, queryset, "read"
        )

        term = (self.request.GET.get("term") or "").strip()
        if term:
            condition = Q()
            for name in registry.get(entity_type).search_fields or ["name"]:
                condition |= Q(**{f"{name}__icontains": term})
            if condition:
                queryset = queryset.filter(condition)

        ordering = registry.get(entity_type).ordering or ["pk"]
        return queryset.order_by(*ordering)


class KanbanView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = ""

    """Kanban board over an entity status field."""

    template_name = "admin/kanban.html"

    def get_context_data(self, **kwargs):
        from omacrm.core.services import kanban

        context = super().get_context_data(**kwargs)
        entity_type = kwargs["entity_type"]
        config = kanban.kanban_config(entity_type)
        if config is None:
            raise Http404("Kanban is not enabled for this entity.")
        if not AclService.check(self.request.user, entity_type, "read"):
            raise PermissionDenied("You cannot read this entity.")

        entity = registry.get(entity_type)
        model = registry.model_for(entity_type)
        meta = model._meta
        board = kanban.board(entity_type, self.request.user)
        for column in board["columns"]:
            cards = []
            for record in column["records"]:
                cards.append(
                    {
                        "pk": record.pk,
                        "label": str(record),
                        "assigned": (
                            record.assigned_user.name
                            if getattr(record, "assigned_user", None)
                            else ""
                        ),
                        "change_url": reverse(
                            f"admin:{meta.app_label}_{meta.model_name}_change",
                            args=[record.pk],
                        ),
                    }
                )
            column["records"] = cards
        context.update(
            {
                "title": _("%(entity)s — Kanban")
                % {"entity": entity.display_label_plural},
                "entity": entity,
                "entity_type": entity_type,
                "config": config,
                "columns": board["columns"],
                "change_list_url": reverse(
                    f"admin:{meta.app_label}_{meta.model_name}_changelist"
                ),
                "move_url": reverse(
                    "kanban_move", kwargs={"entity_type": entity_type}
                ),
            }
        )
        return context


def kanban_move(request, entity_type):
    """Move a record to another Kanban column (JSON endpoint)."""

    from omacrm.core.services import kanban

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required."}, status=405)

    config = kanban.kanban_config(entity_type)
    if config is None:
        return JsonResponse(
            {"ok": False, "error": "Kanban is not enabled for this entity."},
            status=404,
        )

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    model = registry.model_for(entity_type)
    queryset = model.objects.all()
    if registry.is_dynamic(entity_type):
        queryset = queryset.filter(entity_type=entity_type)
    record = queryset.filter(pk=payload.get("pk")).first()
    if record is None:
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)
    if not AclService.check(request.user, entity_type, "edit", record):
        return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)

    try:
        kanban.move_record(
            record, entity_type, config["field"], str(payload.get("value", ""))
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True})


def _parse_json_moment(value):
    """Parse an ISO date/datetime stored in a custom field."""

    from django.utils.dateparse import parse_date, parse_datetime

    if not value or not isinstance(value, str):
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        day = parse_date(value)
        if day is None:
            return None
        parsed = datetime.combine(day, datetime.min.time())
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class LayoutEditorIndexView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = _("Layout Editor")

    template_name = "admin/layout_editor_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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


class LayoutEditorView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = ""

    template_name = "admin/layout_editor_form.html"

    def get_context_data(self, **kwargs):
        import json

        context = super().get_context_data(**kwargs)
        entity_type = kwargs["entity_type"]
        if not registry.has(entity_type):
            raise Http404(f"Unknown entity type: {entity_type}")
        entity = registry.get(entity_type)
        context["title"] = _("Layout Editor: %(entity)s") % {"entity": entity.display_label}
        context["entity_type"] = entity_type
        context["entity"] = entity
        all_fields = {
            **registry.fields(entity_type),
            **registry.link_fields(entity_type),
        }
        context["fields"] = list(all_fields.values())

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

        field_map = all_fields
        sections = []
        if isinstance(detail, list):
            for section in detail:
                if not isinstance(section, dict):
                    continue
                section_fields = []
                for name in section.get("fields", []):
                    field_def = field_map.get(name)
                    if field_def is None:
                        continue
                    section_fields.append(
                        {"name": name, "label": field_def.display_label}
                    )
                sections.append(
                    {"title": str(section.get("title") or ""), "fields": section_fields}
                )
        context["detail_sections"] = sections
        return context

    def post(self, request, *args, **kwargs):
        import json

        from django.contrib import messages
        from django.shortcuts import redirect

        entity_type = kwargs["entity_type"]
        if not registry.has(entity_type):
            raise Http404(f"Unknown entity type: {entity_type}")
        entity = registry.get(entity_type)
        fields = {
            **registry.fields(entity_type),
            **registry.link_fields(entity_type),
        }

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


class RoleAclEditorView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = ""

    template_name = "admin/role_acl_editor.html"

    ACTIONS = ["read", "create", "edit", "delete"]
    LEVELS = ["", "yes", "all", "team", "own", "no"]

    def get_context_data(self, **kwargs):
        from django.shortcuts import get_object_or_404

        from omacrm.core.models import Role

        context = super().get_context_data(**kwargs)
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


def _pending_notifications(user, last_id: int):
    from omacrm.core.models import Notification

    return list(
        Notification.objects.filter(user=user, id__gt=last_id, read=False)
        .order_by("id")
        .values("id", "message", "type")[:10]
    )


def _pending_stream_events(user, last_id: int):
    from omacrm.core.models import StreamEvent

    return list(
        StreamEvent.objects.filter(user=user, id__gt=last_id)
        .order_by("id")
        .values("id", "message")[:10]
    )


def notification_stream(request):
    """Server-sent events with notifications and live stream updates."""

    from omacrm.core.models import Notification, StreamEvent

    user = request.user

    def unread_count():
        return Notification.objects.filter(user=user, read=False).count()

    def latest_id(queryset):
        return queryset.order_by("-id").values_list("id", flat=True).first() or 0

    def events():
        last_notification = latest_id(Notification.objects.filter(user=user))
        last_event = latest_id(StreamEvent.objects.filter(user=user))
        yield f"data: {json.dumps({'type': 'init', 'count': unread_count()})}\n\n"

        # Each connection lives ~5 minutes, then EventSource reconnects.
        for _ in range(100):
            time.sleep(3)
            emitted = False

            notifications = _pending_notifications(user, last_notification)
            if notifications:
                last_notification = notifications[-1]["id"]
                count = unread_count()
                for item in notifications:
                    emitted = True
                    yield "data: " + json.dumps(
                        {
                            "type": "new",
                            "count": count,
                            "id": item["id"],
                            "message": item["message"],
                            "category": item["type"],
                        }
                    ) + "\n\n"

            stream_events = _pending_stream_events(user, last_event)
            if stream_events:
                last_event = stream_events[-1]["id"]
                for item in stream_events:
                    emitted = True
                    yield "data: " + json.dumps(
                        {
                            "type": "stream",
                            "id": item["id"],
                            "message": item["message"],
                        }
                    ) + "\n\n"

            if not emitted:
                yield ": ping\n\n"

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


class GlobalSearchView(UnfoldSiteViewMixin, TemplateView):
    admin_site = admin.site
    permission_required = ()
    title = _("Global Search")

    """Cross-entity text search for staff users (ACL-scoped)."""

    template_name = "admin/global_search.html"
    per_entity_limit = 10

    @staticmethod
    def _is_text_lookup(model, lookup: str) -> bool:
        from django.core.exceptions import FieldDoesNotExist
        from django.db import models as django_models

        segment = lookup.split("__")[0]
        try:
            field = model._meta.get_field(segment)
        except FieldDoesNotExist:
            return False
        if lookup != segment:
            return True
        return isinstance(
            field,
            (
                django_models.CharField,
                django_models.TextField,
                django_models.EmailField,
                django_models.URLField,
            ),
        )

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        from django.urls import NoReverseMatch

        context = super().get_context_data(**kwargs)
        context["title"] = _("Global search")

        query = (self.request.GET.get("q") or "").strip()
        context["query"] = query

        groups = []
        if query:
            user = self.request.user
            for entity_type in registry.entity_types():
                entity = registry.get(entity_type)
                if not entity.search_fields:
                    continue
                if not AclService.check(user, entity_type, "read"):
                    continue

                try:
                    model = registry.model_for(entity_type)
                except LookupError:
                    continue

                condition = Q()
                for lookup in entity.search_fields:
                    if self._is_text_lookup(model, lookup):
                        condition |= Q(**{f"{lookup}__icontains": query})
                for field_def in registry.custom_fields(entity_type):
                    if field_def.type in {"varchar", "text", "email"}:
                        condition |= Q(
                            **{f"custom_data__{field_def.name}__icontains": query}
                        )
                if not condition:
                    continue

                queryset = AclService.scope_queryset(
                    user, entity_type, model.objects.filter(condition), "read"
                )[: self.per_entity_limit]

                results = []
                for obj in queryset:
                    try:
                        url = reverse(
                            f"admin:{model._meta.app_label}_"
                            f"{model._meta.model_name}_change",
                            args=[obj.pk],
                        )
                    except NoReverseMatch:
                        url = ""
                    results.append({"object": obj, "url": url, "label": str(obj)})

                if results:
                    groups.append(
                        {
                            "entity_type": entity_type,
                            "label": entity.display_label_plural,
                            "results": results,
                        }
                    )

        context["groups"] = groups
        context["result_count"] = sum(len(group["results"]) for group in groups)
        return context


def _display_value(value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    return str(value)


class MergeView(TemplateView):
    """Pick field values from two duplicate records and merge them."""

    template_name = "admin/merge.html"

    @property
    def model_admin(self):
        return self.kwargs.get("model_admin")

    def _changelist_url(self):
        meta = self.model_admin.model._meta
        return reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")

    def _rows(self):
        model = self.model_admin.model
        model_fields = {field.name for field in model._meta.concrete_fields}
        rows = []
        for name, field_def in registry.fields(self.model_admin.entity_type).items():
            if field_def.custom or field_def.read_only:
                continue
            if name not in model_fields or name in {"id", "custom_data"}:
                continue
            rows.append((name, field_def))
        return rows

    def _load(self, token):
        session_data = self.request.session.get(f"merge:{token}") if token else None
        if not session_data:
            return None
        pks = session_data.get("pks") or []
        if len(pks) != 2:
            return None
        model = self.model_admin.model
        manager = model.all_objects if hasattr(model, "all_objects") else model.objects
        left = manager.filter(pk=pks[0]).first()
        right = manager.filter(pk=pks[1]).first()
        if left is None or right is None:
            return None
        return left, right

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        context["title"] = _("Merge %(model)s") % {
            "model": self.model_admin.model._meta.verbose_name_plural
        }
        context["changelist_url"] = self._changelist_url()

        token = self.request.GET.get("token") or self.request.POST.get("token") or ""
        context["token"] = token
        loaded = self._load(token)
        context["invalid"] = loaded is None
        if loaded is None:
            return context

        left, right = loaded
        context["left"] = left
        context["right"] = right
        context["rows"] = [
            {
                "name": name,
                "label": field_def.display_label,
                "left_display": _display_value(getattr(left, name, None)),
                "right_display": _display_value(getattr(right, name, None)),
            }
            for name, field_def in self._rows()
        ]
        return context

    def post(self, request, *args, **kwargs):
        from omacrm.core.services.merge import merge_records

        token = request.POST.get("token") or ""
        loaded = self._load(token)
        if loaded is None:
            messages.error(
                request, _("The merge selection expired. Select the records again.")
            )
            return redirect(self._changelist_url())

        left, right = loaded
        master = right if request.POST.get("master") == "right" else left
        duplicate = right if master is left else left

        values = {}
        for name, _field_def in self._rows():
            side = request.POST.get(f"field__{name}")
            source = right if side == "right" else left
            values[name] = getattr(source, name)

        merge_records(master, duplicate, values)
        del request.session[f"merge:{token}"]

        messages.success(
            request,
            _("Records merged. The other record was deleted."),
        )
        meta = master._meta
        return redirect(
            reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[master.pk])
        )


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


class SubscriptionToggleView(View):
    """Toggle the current user's star or follow on one record."""

    http_method_names = ["post"]

    @property
    def model_admin(self):
        return self.kwargs.get("model_admin")

    def post(self, request, kind, object_id, *args, **kwargs):
        from omacrm.core.services import subscriptions

        model_admin = self.model_admin
        obj = model_admin.get_object(request, object_id)
        if obj is None:
            return JsonResponse({"error": "not_found"}, status=404)
        if not model_admin.has_view_permission(request, obj):
            return JsonResponse({"error": "forbidden"}, status=403)

        if kind == "star":
            if not model_admin.supports_stars():
                return JsonResponse({"error": "unsupported"}, status=400)
            value = subscriptions.set_starred(
                request.user, obj, not subscriptions.is_starred(request.user, obj)
            )
        elif kind == "follow":
            if not model_admin.metadata_entity().stream:
                return JsonResponse({"error": "unsupported"}, status=400)
            value = subscriptions.set_following(
                request.user, obj, not subscriptions.is_following(request.user, obj)
            )
        else:
            return JsonResponse({"error": "unknown_kind"}, status=400)

        return JsonResponse({"value": bool(value)})

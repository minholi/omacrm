"""URL configuration for the OmaCRM project."""

from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from omacrm.core.admin.views import (
    CalendarView,
    GlobalSearchView,
    KanbanView,
    LayoutEditorIndexView,
    LayoutEditorView,
    RoleAclEditorView,
    kanban_move,
    notification_stream,
)
from omacrm.core.api.router import router
from omacrm.core.api.viewsets import DynamicRecordViewSet
from omacrm.crm import views as crm_views

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path(
        "admin/calendar/",
        admin.site.admin_view(CalendarView.as_view()),
        name="crm_calendar",
    ),
    path(
        "admin/layout-editor/",
        admin.site.admin_view(LayoutEditorIndexView.as_view()),
        name="layout_editor_index",
    ),
    path(
        "admin/layout-editor/<str:entity_type>/",
        admin.site.admin_view(LayoutEditorView.as_view()),
        name="layout_editor",
    ),
    path(
        "admin/access/role/<int:pk>/",
        admin.site.admin_view(RoleAclEditorView.as_view()),
        name="role_acl_editor",
    ),
    path(
        "admin/notifications/stream/",
        admin.site.admin_view(notification_stream),
        name="notification_stream",
    ),
    path(
        "admin/global-search/",
        admin.site.admin_view(GlobalSearchView.as_view()),
        name="global_search",
    ),
    path(
        "admin/kanban/<str:entity_type>/",
        admin.site.admin_view(KanbanView.as_view()),
        name="kanban_board",
    ),
    path(
        "admin/kanban/<str:entity_type>/move/",
        admin.site.admin_view(kanban_move),
        name="kanban_move",
    ),
    path(
        "campaigns/track/<int:pk>/",
        crm_views.campaign_track_click,
        name="campaign_track_click",
    ),
    path(
        "campaigns/open/<int:pk>/",
        crm_views.campaign_track_open,
        name="campaign_track_open",
    ),
    path(
        "events/confirm/<int:pk>/<str:action>/<str:token>/",
        crm_views.event_confirmation,
        name="event_confirmation",
    ),
    path(
        "api/v1/lead-capture/<str:api_key>/",
        crm_views.lead_capture,
        name="lead_capture",
    ),
    path(
        "lead-capture/confirm/<str:token>/",
        crm_views.lead_capture_confirm,
        name="lead_capture_confirm",
    ),
    path(
        "unsubscribe/<str:token>/",
        crm_views.mass_email_unsubscribe,
        name="mass_email_unsubscribe",
    ),
    path("admin/", admin.site.urls),
    path("portal/", include("omacrm.crm.portal_urls")),
    path("hijack/", include("hijack.urls")),
    re_path(
        r"^api/v1/(?P<entity_type>[A-Z][A-Za-z0-9]*)/$",
        DynamicRecordViewSet.as_view({"get": "list", "post": "create"}),
        name="dynamic-entity-list",
    ),
    re_path(
        r"^api/v1/(?P<entity_type>[A-Z][A-Za-z0-9]*)/(?P<pk>[^/.]+)/$",
        DynamicRecordViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="dynamic-entity-detail",
    ),
    path("api/v1/", include(router.urls)),
]

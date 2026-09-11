"""URL configuration for the OmaCRM project."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from omacrm.core.admin.views import (
    CalendarView,
    LayoutEditorIndexView,
    LayoutEditorView,
    RoleAclEditorView,
    notification_stream,
)
from omacrm.core.api.router import router
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
        "api/v1/lead-capture/<str:api_key>/",
        crm_views.lead_capture,
        name="lead_capture",
    ),
    path("admin/", admin.site.urls),
    path("portal/", include("omacrm.crm.portal_urls")),
    path("hijack/", include("hijack.urls")),
    path("api/v1/", include(router.urls)),
]

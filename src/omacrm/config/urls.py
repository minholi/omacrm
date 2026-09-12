"""URL configuration for the OmaCRM project."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve as static_serve

from omacrm.core.admin.views import (
    CalendarView,
    GlobalSearchView,
    KanbanView,
    LayoutEditorIndexView,
    LayoutEditorView,
    LinkAutocompleteView,
    RoleAclEditorView,
    kanban_move,
    notification_stream,
)
from omacrm.core.api.router import router
from omacrm.core.api.viewsets import DynamicRecordViewSet
from omacrm.crm import views as crm_views
from omacrm.crm.admin_views import (
    EmailTemplateDesignView,
    EmailTemplateSourceView,
    email_asset_upload,
    email_template_compile,
    email_template_design_save,
    email_template_preview,
    email_template_source_save,
    email_template_test_send,
)
from omacrm.crm import views as crm_views

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path(
        "admin/email-assets/upload/",
        admin.site.admin_view(email_asset_upload),
        name="email_asset_upload",
    ),
    path(
        "admin/email-template/<int:pk>/design/",
        admin.site.admin_view(EmailTemplateDesignView.as_view()),
        name="email_template_design",
    ),
    path(
        "admin/email-template/<int:pk>/design/save/",
        admin.site.admin_view(email_template_design_save),
        name="email_template_design_save",
    ),
    path(
        "admin/email-template/<int:pk>/preview/",
        admin.site.admin_view(email_template_preview),
        name="email_template_preview",
    ),
    path(
        "admin/email-template/<int:pk>/test-send/",
        admin.site.admin_view(email_template_test_send),
        name="email_template_test_send",
    ),
    path(
        "admin/email-template/<int:pk>/source/",
        admin.site.admin_view(EmailTemplateSourceView.as_view()),
        name="email_template_source",
    ),
    path(
        "admin/email-template/<int:pk>/source/save/",
        admin.site.admin_view(email_template_source_save),
        name="email_template_source_save",
    ),
    path(
        "admin/email-template/<int:pk>/compile/",
        admin.site.admin_view(email_template_compile),
        name="email_template_compile",
    ),
    path(
        "admin/calendar/",
        admin.site.admin_view(CalendarView.as_view(admin_site=admin.site)),
        name="crm_calendar",
    ),
    path(
        "admin/layout-editor/",
        admin.site.admin_view(LayoutEditorIndexView.as_view(admin_site=admin.site)),
        name="layout_editor_index",
    ),
    path(
        "admin/layout-editor/<str:entity_type>/",
        admin.site.admin_view(LayoutEditorView.as_view(admin_site=admin.site)),
        name="layout_editor",
    ),
    path(
        "admin/access/role/<int:pk>/",
        admin.site.admin_view(RoleAclEditorView.as_view(admin_site=admin.site)),
        name="role_acl_editor",
    ),
    path(
        "admin/notifications/stream/",
        admin.site.admin_view(notification_stream),
        name="notification_stream",
    ),
    path(
        "admin/global-search/",
        admin.site.admin_view(GlobalSearchView.as_view(admin_site=admin.site)),
        name="global_search",
    ),
    path(
        "admin/kanban/<str:entity_type>/",
        admin.site.admin_view(KanbanView.as_view(admin_site=admin.site)),
        name="kanban_board",
    ),
    path(
        "admin/link-autocomplete/",
        admin.site.admin_view(LinkAutocompleteView.as_view()),
        name="link_autocomplete",
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

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
            static_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

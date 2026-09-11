"""
Django settings for the OmaCRM project.

Runtime baseline: Python 3.13 / Django 5.2 LTS / django-unfold 0.105+.
The Unfold admin is the primary application interface.
"""

import os
from pathlib import Path

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from unfold.contrib.constance.settings import UNFOLD_CONSTANCE_ADDITIONAL_FIELDS

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-062ns&b_%v5a)shvaz&k4vk3&hwww^k^oyb@))$6qpqx1ge!)e",
)

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # Unfold must precede django.contrib.admin and its integrations must
    # precede the packages they restyle.
    "unfold",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.simple_history",
    "unfold.contrib.constance",
    "unfold.contrib.hijack",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party.
    "simple_history",
    "import_export",
    "djangoql",
    "constance",
    "constance.backends.database",
    "hijack",
    "hijack.contrib.admin",
    "djmoney",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    # Local.
    "omacrm.core",
    "omacrm.crm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "omacrm.core.middleware.CurrentUserMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "omacrm.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "omacrm.config.wsgi.application"
ASGI_APPLICATION = "omacrm.config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEST_RUNNER = "omacrm.config.test_runner.OmacrmDiscoverRunner"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "OmaCRM <noreply@omacrm.local>"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"

# ---------------------------------------------------------------------------
# django-constance (global platform settings, editable in the admin)
# ---------------------------------------------------------------------------

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_ADDITIONAL_FIELDS = {
    **UNFOLD_CONSTANCE_ADDITIONAL_FIELDS,
}

CONSTANCE_CONFIG = {
    "company_name": ("OmaCRM", "Company name shown in the UI", str),
    "records_per_page": (20, "Default number of records per page", int),
    "base_currency": ("USD", "Base currency for monetary amounts", str),
    "default_currency": ("USD", "Default currency for new records", str),
    "date_format": ("Y-m-d", "Date format (Django syntax)", str),
    "time_format": ("H:i", "Time format (Django syntax)", str),
    "phone_default_region": (
        "US",
        "Default region (ISO country code) used to parse phone numbers",
        str,
    ),
    "notification_email_enabled": (
        True,
        "Email unread notifications as a digest",
        bool,
    ),
}

CONSTANCE_CONFIG_FIELDSETS = {
    "General": ("company_name", "records_per_page"),
    "Currency & Formats": (
        "base_currency",
        "default_currency",
        "date_format",
        "time_format",
    ),
    "Localization": ("phone_default_region",),
    "Notifications": ("notification_email_enabled",),
}

# ---------------------------------------------------------------------------
# Third-party integrations
# ---------------------------------------------------------------------------

IMPORT_EXPORT_USE_TRANSACTIONS = True

DEFAULT_CURRENCY = "USD"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

# ---------------------------------------------------------------------------
# Unfold (primary admin UI)
# ---------------------------------------------------------------------------

UNFOLD = {
    "SITE_TITLE": "OmaCRM",
    "SITE_HEADER": "OmaCRM",
    "SITE_URL": "/",
    "SITE_SYMBOL": "hub",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "href": "/static/core/favicon.svg",
            "type": "image/svg+xml",
        }
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "omacrm.core.admin.dashboard.dashboard_callback",
    "ENVIRONMENT": "omacrm.core.admin.dashboard.environment_callback",
    "COMMAND": {
        "search_models": True,
        "show_history": True,
    },
    "SCRIPTS": ["/static/core/js/notifications.js"],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Sales"),
                "collapsible": True,
                "separator": True,
                "items": [
                    {"title": _("Accounts"), "icon": "domain", "link": reverse_lazy("admin:crm_account_changelist")},
                    {"title": _("Contacts"), "icon": "contacts", "link": reverse_lazy("admin:crm_contact_changelist")},
                    {"title": _("Leads"), "icon": "person_add", "link": reverse_lazy("admin:crm_lead_changelist")},
                    {"title": _("Opportunities"), "icon": "trending_up", "link": reverse_lazy("admin:crm_opportunity_changelist")},
                    {"title": _("Tasks"), "icon": "task_alt", "link": reverse_lazy("admin:crm_task_changelist")},
                    {"title": _("Documents"), "icon": "description", "link": reverse_lazy("admin:crm_document_changelist")},
                ],
            },
            {
                "title": _("Support"),
                "collapsible": True,
                "items": [
                    {"title": _("Cases"), "icon": "support_agent", "link": reverse_lazy("admin:crm_case_changelist")},
                    {"title": _("Knowledge Base"), "icon": "menu_book", "link": reverse_lazy("admin:crm_knowledgebasearticle_changelist")},
                ],
            },
            {
                "title": _("Marketing"),
                "collapsible": True,
                "items": [
                    {"title": _("Campaigns"), "icon": "campaign", "link": reverse_lazy("admin:crm_campaign_changelist")},
                    {"title": _("Target Lists"), "icon": "format_list_bulleted", "link": reverse_lazy("admin:crm_targetlist_changelist")},
                    {"title": _("Mass Emails"), "icon": "mail", "link": reverse_lazy("admin:crm_massemail_changelist")},
                    {"title": _("Lead Capture"), "icon": "webhook", "link": reverse_lazy("admin:crm_leadcapture_changelist")},
                ],
            },
            {
                "title": _("Activities"),
                "collapsible": True,
                "items": [
                    {"title": _("Calendar"), "icon": "calendar_month", "link": reverse_lazy("crm_calendar")},
                    {"title": _("Calls"), "icon": "call", "link": reverse_lazy("admin:crm_call_changelist")},
                    {"title": _("Meetings"), "icon": "event", "link": reverse_lazy("admin:crm_meeting_changelist")},
                ],
            },
            {
                "title": _("Administration"),
                "collapsible": True,
                "separator": True,
                "items": [
                    {"title": _("Users"), "icon": "person", "link": reverse_lazy("admin:core_user_changelist")},
                    {"title": _("Teams"), "icon": "groups", "link": reverse_lazy("admin:core_team_changelist")},
                    {"title": _("Roles"), "icon": "shield_person", "link": reverse_lazy("admin:core_role_changelist")},
                    {"title": _("Preferences"), "icon": "tune", "link": reverse_lazy("admin:core_preferences_changelist")},
                ],
            },
            {
                "title": _("Customization"),
                "collapsible": True,
                "items": [
                    {"title": _("Custom Fields"), "icon": "add_box", "link": reverse_lazy("admin:core_customfield_changelist")},
                    {"title": _("Layouts"), "icon": "view_column", "link": reverse_lazy("admin:core_layout_changelist")},
                    {"title": _("Layout Editor"), "icon": "dashboard_customize", "link": reverse_lazy("layout_editor_index")},
                    {"title": _("Custom Entities"), "icon": "extension", "link": reverse_lazy("admin:core_customentity_changelist")},
                    {"title": _("Formulas"), "icon": "function", "link": reverse_lazy("admin:core_formula_changelist")},
                    {"title": _("Workflows"), "icon": "account_tree", "link": reverse_lazy("admin:core_workflow_changelist")},
                ],
            },
            {
                "title": _("System"),
                "collapsible": True,
                "items": [
                    {"title": _("Jobs"), "icon": "pending_actions", "link": reverse_lazy("admin:core_job_changelist")},
                    {"title": _("Scheduled Jobs"), "icon": "schedule", "link": reverse_lazy("admin:core_scheduledjob_changelist")},
                    {"title": _("Email Templates"), "icon": "mail", "link": reverse_lazy("admin:crm_emailtemplate_changelist")},
                    {"title": _("Currencies"), "icon": "currency_exchange", "link": reverse_lazy("admin:core_currency_changelist")},
                    {"title": _("Webhooks"), "icon": "webhook", "link": reverse_lazy("admin:core_webhook_changelist")},
                    {"title": _("Notes"), "icon": "forum", "link": reverse_lazy("admin:core_note_changelist")},
                    {"title": _("Notifications"), "icon": "notifications", "badge": "omacrm.core.admin.dashboard.unread_notifications_badge", "link": reverse_lazy("admin:core_notification_changelist")},
                    {"title": _("Settings"), "icon": "settings", "link": reverse_lazy("admin:constance_config_changelist")},
                ],
            },
        ],
    },
    "ACCOUNT": {
        "navigation": [],
    },
}

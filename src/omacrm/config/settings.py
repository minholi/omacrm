"""
Django settings for the OmaCRM project.

Runtime baseline: Python 3.13 / Django 5.2 LTS / django-unfold 0.105+.
The Unfold admin is the primary application interface.
"""

import os
from pathlib import Path

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
    "unfold.contrib.filters",
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
    "currency_rates_url": (
        "",
        "JSON endpoint with rates relative to the base currency "
        "(a `rates`/`conversion_rates` map); empty disables the sync job",
        str,
    ),
    "date_format": ("Y-m-d", "Date format (Django syntax)", str),
    "time_format": ("H:i", "Time format (Django syntax)", str),
    "phone_default_region": (
        "US",
        "Default region (ISO country code) used to parse phone numbers",
        str,
    ),
    "public_base_url": (
        "",
        "Absolute base URL used to turn relative links and images (e.g. "
        "/media/...) into absolute URLs in outgoing emails; empty disables it",
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
        "currency_rates_url",
        "date_format",
        "time_format",
    ),
    "Localization": ("phone_default_region",),
    "Email": ("public_base_url",),
    "Notifications": ("notification_email_enabled",),
}

# ---------------------------------------------------------------------------
# Third-party integrations
# ---------------------------------------------------------------------------

IMPORT_EXPORT_USE_TRANSACTIONS = True

DEFAULT_CURRENCY = "USD"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "omacrm.core.api.auth.ApiKeyAuthentication",
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
        "search_callback": "omacrm.core.services.command_palette.command_search",
    },
    "SCRIPTS": ["/static/core/js/notifications.js"],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": "omacrm.core.services.navigation.sidebar_navigation",
    },
    "ACCOUNT": {
        "navigation": [],
    },
}

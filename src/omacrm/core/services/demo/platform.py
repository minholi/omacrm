"""Platform-level demo data: users, teams, roles, portal, jobs, currencies."""

import secrets

from django.contrib.auth import get_user_model

from omacrm.core.models import (
    Currency,
    EmailAccount,
    PortalRole,
    Preferences,
    Role,
    ScheduledJob,
    Team,
    TeamUser,
)
from omacrm.core.services.currency import set_rate
from omacrm.crm.models import Contact

from .common import date_in, make_rng

DEFAULT_ROLE_DATA = {
    entity: {
        "read": "all",
        "create": "yes",
        "edit": "all",
        "delete": "team",
    }
    for entity in [
        "Account",
        "Contact",
        "Lead",
        "Opportunity",
        "Task",
        "Call",
        "Meeting",
        "Case",
    ]
}

SUPPORT_ROLE_DATA = {
    "Case": {"read": "all", "create": "yes", "edit": "all", "delete": "no"},
    "KnowledgeBaseArticle": {
        "read": "all",
        "create": "yes",
        "edit": "all",
        "delete": "no",
    },
}

PORTAL_ROLE_DATA = {
    "Case": {"read": "own", "create": "yes", "edit": "own"},
    "KnowledgeBaseArticle": {"read": "all"},
    "Document": {"read": "own"},
}

EXTRA_USERS = (
    ("ana.souza", "Ana", "Souza", "ana.souza@example.com"),
    ("bruno.almeida", "Bruno", "Almeida", "bruno.almeida@example.com"),
    ("carla.mendes", "Carla", "Mendes", "carla.mendes@example.com"),
    ("api.bot", "API", "Bot", "api.bot@example.com"),
)

SCHEDULED_JOBS = (
    ("Cleanup old jobs", "system.cleanup_jobs", "0 3 * * *"),
    ("Send reminders", "crm.send_reminders", "* * * * *"),
    ("Control knowledge base status", "crm.control_kb_article_status", "10 1 * * *"),
    ("Process webhooks", "core.process_webhooks", "*/2 * * * *"),
    ("Send notification emails", "core.send_notification_emails", "*/5 * * * *"),
    ("Fetch inbound email", "core.fetch_inbound_email", "*/5 * * * *"),
    ("Sync currency rates", "core.sync_currency_rates", "15 2 * * *"),
    ("Cleanup stream events", "core.cleanup_stream_events", "30 3 * * *"),
)

CURRENCIES = (
    ("USD", "US Dollar", "$"),
    ("EUR", "Euro", "€"),
    ("BRL", "Brazilian Real", "R$"),
    ("GBP", "British Pound", "£"),
)

RATE_HISTORY = {
    # Value of one unit of the currency in the base currency (USD).
    "EUR": [0.89, 0.90, 0.91, 0.90, 0.92, 0.93, 0.92, 0.94, 0.93, 0.92, 0.91, 0.92],
    "BRL": [0.196, 0.194, 0.191, 0.189, 0.190, 0.187, 0.185, 0.182, 0.183, 0.184, 0.186, 0.185],
    "GBP": [1.30, 1.28, 1.27, 1.28, 1.25, 1.23, 1.25, 1.22, 1.23, 1.27, 1.28, 1.27],
}


def _merge_role_data(role, data: dict) -> None:
    """Add missing entity scopes without overriding edited levels."""

    merged = dict(role.data or {})
    changed = False
    for entity_type, actions in data.items():
        scope = dict(merged.get(entity_type) or {})
        for action, level in actions.items():
            if action not in scope:
                scope[action] = level
                changed = True
        if scope != (merged.get(entity_type) or {}):
            merged[entity_type] = scope
    if changed:
        role.data = merged
        role.save(update_fields=["data"])


def _user(defaults, user_name, **extra):
    User = get_user_model()
    user = User.objects.filter(user_name=user_name).first()
    if user is None:
        user = User.objects.create_user(user_name, defaults.pop("email"), **defaults)
    for key, value in extra.items():
        setattr(user, key, value)
    user.save()
    return user


def seed_platform(*, password="demo12345", admin_password="admin12345", rng_seed=42):
    """Create users, teams, portal access, jobs, currencies and rates."""

    rng = make_rng(rng_seed)

    admin_role, _ = Role.objects.get_or_create(
        name="Administrator", defaults={"description": "Full access"}
    )
    sales_role, _ = Role.objects.get_or_create(
        name="Sales Manager",
        defaults={
            "description": "Full access to sales entities",
            "data": DEFAULT_ROLE_DATA,
        },
    )
    support_role, _ = Role.objects.get_or_create(
        name="Support Agent",
        defaults={
            "description": "Case and knowledge base access",
            "data": SUPPORT_ROLE_DATA,
        },
    )

    sales_team, _ = Team.objects.get_or_create(name="Sales")
    sales_team.roles.add(sales_role)
    support_team, _ = Team.objects.get_or_create(name="Support")
    support_team.roles.add(support_role)
    _merge_role_data(sales_role, DEFAULT_ROLE_DATA)
    _merge_role_data(support_role, SUPPORT_ROLE_DATA)

    User = get_user_model()
    admin = User.objects.filter(user_name="admin").first()
    if admin is None:
        admin = User.objects.create_superuser(
            "admin", "admin@example.com", admin_password
        )
    admin.roles.add(admin_role)

    demo = _user(
        {"email": "demo@example.com", "password": password},
        "demo",
        first_name="Demo",
        last_name="User",
        is_staff=True,
        is_active=True,
        type=User.Type.REGULAR,
        default_team=sales_team,
    )
    demo.set_password(password)
    demo.save()
    demo.roles.add(sales_role)
    TeamUser.objects.get_or_create(
        team=sales_team, user=demo, defaults={"role": "Account Executive"}
    )

    users = {"admin": admin, "demo": demo}
    for user_name, first, last, email in EXTRA_USERS:
        user = _user(
            {"email": email, "password": password},
            user_name,
            first_name=first,
            last_name=last,
            is_active=True,
            is_staff=False,
        )
        user.set_password(password)
        if user_name == "carla.mendes":
            user.type = User.Type.REGULAR
            user.default_team = support_team
            user.roles.add(support_role)
            TeamUser.objects.get_or_create(
                team=support_team, user=user, defaults={"role": "Support Agent"}
            )
        elif user_name == "api.bot":
            user.type = User.Type.API
            user.api_key = secrets.token_hex(32)
        else:
            user.type = User.Type.REGULAR
            user.default_team = sales_team
            user.roles.add(sales_role)
            TeamUser.objects.get_or_create(
                team=sales_team, user=user, defaults={"role": "Sales Rep"}
            )
        user.save()
        users[user_name] = user

    for user in users.values():
        Preferences.objects.get_or_create(user=user)

    for name, job, scheduling in SCHEDULED_JOBS:
        ScheduledJob.objects.get_or_create(
            name=name, defaults={"job": job, "scheduling": scheduling}
        )

    for code, name, symbol in CURRENCIES:
        Currency.objects.get_or_create(
            code=code, defaults={"name": name, "symbol": symbol}
        )

    for code, series in RATE_HISTORY.items():
        for offset, rate in enumerate(series):
            set_rate(code, rate, date=date_in(-30 * (len(series) - 1 - offset)))
        currency = Currency.objects.get(code=code)
        currency.rate = series[-1]
        currency.save(update_fields=["rate", "updated_at"])

    account = EmailAccount.objects.filter(name="Demo IMAP (inactive)").first()
    if account is None:
        account = EmailAccount(
            name="Demo IMAP (inactive)",
            email_address="support@example.com",
            imap_host="imap.example.com",
            imap_username="support@example.com",
            folder="INBOX, Sent",
            is_active=False,
            default_assigned_user=demo,
        )
        account.set_password("demo-imap-password")
        account.save()

    portal_role, _ = PortalRole.objects.get_or_create(
        name="Customer",
        defaults={
            "description": "Default customer-portal access",
            "data": PORTAL_ROLE_DATA,
        },
    )
    portal_contact, _ = Contact.objects.get_or_create(
        first_name="Paula",
        last_name="Portal",
        defaults={"email_address": "portal@example.com", "title": "IT Manager"},
    )
    portal_user = User.objects.filter(user_name="portal").first()
    if portal_user is None:
        portal_user = User.objects.create_user(
            "portal", "portal@example.com", "portal12345"
        )
    portal_user.first_name = "Paula"
    portal_user.last_name = "Portal"
    portal_user.type = User.Type.PORTAL
    portal_user.set_password("portal12345")
    portal_user.save()
    portal_user.portal_roles.add(portal_role)
    portal_contact.portal_user = portal_user
    portal_contact.save(update_fields=["portal_user"])

    return {
        "rng": rng,
        "users": users,
        "admin": admin,
        "demo": demo,
        "ana": users["ana.souza"],
        "bruno": users["bruno.almeida"],
        "carla": users["carla.mendes"],
        "api_user": users["api.bot"],
        "sales_team": sales_team,
        "support_team": support_team,
        "sales_role": sales_role,
        "support_role": support_role,
        "portal_user": portal_user,
        "portal_contact": portal_contact,
    }

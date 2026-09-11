from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from omacrm.core.models import (
    Currency,
    PortalRole,
    Preferences,
    Role,
    ScheduledJob,
    Team,
    TeamUser,
)
from omacrm.crm.models import Contact, EmailTemplate

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


class Command(BaseCommand):
    help = "Seed demo users, teams, roles and scheduled jobs."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo12345")
        parser.add_argument("--admin-password", default="admin12345")

    def handle(self, *args, **options):
        User = get_user_model()
        password = options["password"]

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
        sales_team, _ = Team.objects.get_or_create(name="Sales")
        sales_team.roles.add(sales_role)

        admin = User.objects.filter(user_name="admin").first()
        if admin is None:
            admin = User.objects.create_superuser(
                "admin", "admin@example.com", options["admin_password"]
            )
            self.stdout.write(self.style.SUCCESS("Created admin user (admin)"))
        admin.roles.add(admin_role)

        demo = User.objects.filter(user_name="demo").first()
        if demo is None:
            demo = User.objects.create_user("demo", "demo@example.com", password)
            demo.first_name = "Demo"
            demo.last_name = "User"
            demo.is_staff = True
            demo.default_team = sales_team
            demo.save()
            self.stdout.write(
                self.style.SUCCESS(f"Created demo user (demo / {password})")
            )
        TeamUser.objects.get_or_create(team=sales_team, user=demo, defaults={"role": "Sales"})
        demo.roles.add(sales_role)

        for user in (admin, demo):
            Preferences.objects.get_or_create(user=user)

        ScheduledJob.objects.get_or_create(
            name="Cleanup old jobs",
            defaults={"job": "system.cleanup_jobs", "scheduling": "0 3 * * *"},
        )
        ScheduledJob.objects.get_or_create(
            name="Send reminders",
            defaults={"job": "crm.send_reminders", "scheduling": "* * * * *"},
        )
        ScheduledJob.objects.get_or_create(
            name="Control knowledge base status",
            defaults={
                "job": "crm.control_kb_article_status",
                "scheduling": "10 1 * * *",
            },
        )
        ScheduledJob.objects.get_or_create(
            name="Process webhooks",
            defaults={"job": "core.process_webhooks", "scheduling": "*/2 * * * *"},
        )
        ScheduledJob.objects.get_or_create(
            name="Send notification emails",
            defaults={
                "job": "core.send_notification_emails",
                "scheduling": "*/5 * * * *",
            },
        )
        ScheduledJob.objects.get_or_create(
            name="Fetch inbound email",
            defaults={
                "job": "core.fetch_inbound_email",
                "scheduling": "*/5 * * * *",
            },
        )

        for code, name, symbol, rate in (
            ("USD", "US Dollar", "$", "1"),
            ("EUR", "Euro", "€", "0.92"),
            ("BRL", "Brazilian Real", "R$", "5.40"),
        ):
            Currency.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "symbol": symbol,
                    "rate": Decimal(rate),
                },
            )

        EmailTemplate.objects.get_or_create(
            name="Welcome",
            defaults={
                "subject": "Hello {{ name }}",
                "body": (
                    "<p>Dear {{ name }},</p>"
                    "<p>Thank you for your interest in {{ record.website|default:'our company' }}.</p>"
                ),
            },
        )

        portal_role, _ = PortalRole.objects.get_or_create(
            name="Customer",
            defaults={
                "description": "Default customer-portal access",
                "data": {
                    "Case": {"read": "own", "create": "yes", "edit": "own"},
                    "KnowledgeBaseArticle": {"read": "all"},
                },
            },
        )
        portal_contact, _ = Contact.objects.get_or_create(
            first_name="Portal",
            last_name="Customer",
            defaults={"email_address": "portal@example.com"},
        )
        portal_user = User.objects.filter(user_name="portal").first()
        if portal_user is None:
            portal_user = User.objects.create_user(
                "portal", "portal@example.com", "portal12345"
            )
            portal_user.first_name = "Portal"
            portal_user.last_name = "Customer"
            portal_user.type = User.Type.PORTAL
            portal_user.save()
            self.stdout.write(
                self.style.SUCCESS("Created portal user (portal / portal12345)")
            )
        portal_user.portal_roles.add(portal_role)
        portal_contact.portal_user = portal_user
        portal_contact.save(update_fields=["portal_user"])

        self.stdout.write(self.style.SUCCESS("Demo data ready."))

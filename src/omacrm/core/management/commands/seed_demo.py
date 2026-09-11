from django.core.management.base import BaseCommand

from omacrm.core.models import DynamicRecord
from omacrm.core.services.demo import seed_all
from omacrm.crm.models import Account, Campaign, Case, Contact, Document, Lead, Opportunity


class Command(BaseCommand):
    help = "Seed demo users and a rich dataset showcasing every CRM feature."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo business data and rebuild it.",
        )
        parser.add_argument(
            "--rng-seed",
            type=int,
            default=42,
            help="Random seed used for generated values (default: 42).",
        )
        parser.add_argument(
            "--base-url",
            default="",
            help="Base URL used for links (invitations, tracking) in demo data.",
        )
        parser.add_argument("--password", default="demo12345")
        parser.add_argument("--admin-password", default="admin12345")

    def handle(self, *args, **options):
        reset = options["reset"]
        if not reset and Account.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Business data already exists; nothing to do. "
                    "Run with --reset to rebuild the demo dataset."
                )
            )
            return

        seed_all(
            stdout=self.stdout,
            reset=reset,
            rng_seed=options["rng_seed"],
            base_url=options["base_url"],
            password=options["password"],
            admin_password=options["admin_password"],
        )

        counts = {
            "accounts": Account.objects.count(),
            "contacts": Contact.objects.count(),
            "leads": Lead.objects.count(),
            "opportunities": Opportunity.objects.count(),
            "cases": Case.objects.count(),
            "documents": Document.objects.count(),
            "campaigns": Campaign.objects.count(),
            "projects": DynamicRecord.objects.filter(entity_type="Project").count(),
        }
        summary = ", ".join(f"{value} {key}" for key, value in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {summary}."))
        self.stdout.write(
            "Logins: admin/admin12345, demo/demo12345, portal/portal12345 "
            "(portal at /portal/)."
        )
        self.stdout.write(
            "Note: custom entity 'Project' admin/API pages appear after a "
            "server restart."
        )

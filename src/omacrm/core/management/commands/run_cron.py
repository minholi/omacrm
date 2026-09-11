from django.core.management.base import BaseCommand

from omacrm.core.services.jobs import JobRunner


class Command(BaseCommand):
    help = "Enqueue due scheduled jobs and (optionally) process the queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--process",
            action="store_true",
            help="Process pending jobs immediately after scheduling.",
        )

    def handle(self, *args, **options):
        scheduled = JobRunner.run_due_scheduled_jobs()
        self.stdout.write(self.style.SUCCESS(f"Enqueued {scheduled} scheduled job(s)"))
        if options["process"]:
            processed = JobRunner.run_pending()
            self.stdout.write(self.style.SUCCESS(f"Processed {processed} job(s)"))

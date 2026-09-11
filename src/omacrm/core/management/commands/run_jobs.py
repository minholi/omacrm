import time

from django.core.management.base import BaseCommand

from omacrm.core.services.jobs import JobRunner


class Command(BaseCommand):
    help = "Process pending background jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Maximum jobs per pass.")
        parser.add_argument("--queue", default=None, help="Only process this queue.")
        parser.add_argument("--loop", action="store_true", help="Keep running.")
        parser.add_argument(
            "--interval", type=float, default=5.0, help="Seconds between passes with --loop."
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        queue = options["queue"]
        loop = options["loop"]
        interval = options["interval"]

        while True:
            processed = JobRunner.run_pending(limit=limit, queue=queue)
            if processed:
                self.stdout.write(self.style.SUCCESS(f"Processed {processed} job(s)"))
            elif not loop:
                self.stdout.write("No pending jobs.")
            if not loop:
                return
            time.sleep(interval)

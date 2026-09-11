import logging
from datetime import datetime, timedelta

from croniter import croniter
from django.utils import timezone

from omacrm.core.models import Job, ScheduledJob, ScheduledJobLog

logger = logging.getLogger(__name__)


class JobRegistry:
    """Maps job keys to callables. Callables receive the ``Job`` row."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}

    def register(self, key: str, name: str | None = None):
        def decorator(func):
            self._jobs[key] = {"key": key, "name": name or key, "func": func}
            return func

        return decorator

    def get(self, key: str):
        return self._jobs.get(key)

    def keys(self) -> list[str]:
        return sorted(self._jobs)


jobs = JobRegistry()


def schedule(
    job_key: str,
    data: dict | None = None,
    execute_time=None,
    name: str | None = None,
    queue: str = "default",
) -> Job:
    entry = jobs.get(job_key)
    return Job.objects.create(
        name=name or (entry["name"] if entry else job_key),
        class_name=job_key,
        data=data or {},
        queue=queue,
        execute_time=execute_time or timezone.now(),
    )


class JobRunner:
    RETRY_DELAY_SECONDS = 300

    @classmethod
    def run_job(cls, job: Job) -> Job:
        entry = jobs.get(job.class_name)
        job.status = Job.Status.RUNNING
        job.started_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=["status", "started_at", "attempts"])

        if entry is None:
            job.status = Job.Status.FAILED
            job.last_error = f"No handler registered for job '{job.class_name}'"
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "last_error", "finished_at"])
            return job

        try:
            entry["func"](job)
        except Exception as exc:  # noqa: BLE001 - persist any handler failure
            logger.exception("Job %s failed", job.pk)
            job.last_error = str(exc)
            if job.attempts < job.max_attempts:
                job.status = Job.Status.PENDING
                job.execute_time = timezone.now() + timedelta(
                    seconds=cls.RETRY_DELAY_SECONDS * job.attempts
                )
                job.save(
                    update_fields=["status", "last_error", "execute_time", "finished_at"]
                )
            else:
                job.status = Job.Status.FAILED
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "last_error", "finished_at"])
            return job

        job.status = Job.Status.SUCCESS
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
        return job

    @classmethod
    def run_pending(cls, limit: int = 50, queue: str | None = None) -> int:
        now = timezone.now()
        queryset = Job.objects.filter(
            status=Job.Status.PENDING,
            execute_time__lte=now,
        ).order_by("execute_time", "id")
        if queue:
            queryset = queryset.filter(queue=queue)

        processed = 0
        for job in list(queryset[:limit]):
            cls.run_job(job)
            processed += 1
        return processed

    @classmethod
    def run_due_scheduled_jobs(cls, now=None) -> int:
        now = now or timezone.now()
        created = 0
        for scheduled_job in ScheduledJob.objects.filter(is_active=True):
            if not croniter.is_valid(scheduled_job.scheduling):
                ScheduledJobLog.objects.create(
                    scheduled_job=scheduled_job,
                    status="Invalid",
                    message=f"Invalid cron expression: {scheduled_job.scheduling}",
                )
                continue

            base = scheduled_job.last_run or (now - timedelta(minutes=1))
            next_run = croniter(scheduled_job.scheduling, base).get_next(datetime)
            if next_run <= now:
                schedule(
                    scheduled_job.job,
                    data=scheduled_job.data,
                    name=scheduled_job.name,
                )
                scheduled_job.last_run = now
                scheduled_job.last_status = "Scheduled"
                scheduled_job.save(update_fields=["last_run", "last_status"])
                ScheduledJobLog.objects.create(
                    scheduled_job=scheduled_job, status="Scheduled"
                )
                created += 1
        return created

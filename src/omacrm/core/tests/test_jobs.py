from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from omacrm.core.models import Job, ScheduledJob
from omacrm.core.services.jobs import JobRunner, jobs, schedule


class JobRunnerTests(TestCase):
    def test_successful_job(self):
        calls = []

        @jobs.register("test.success")
        def handler(job):
            calls.append(job.pk)

        job = schedule("test.success")
        JobRunner.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.SUCCESS)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(calls, [job.pk])
        self.assertIsNotNone(job.finished_at)

    def test_failing_job_retries_then_fails(self):
        @jobs.register("test.fail")
        def handler(job):
            raise ValueError("boom")

        job = schedule("test.fail", name="Failing job")
        JobRunner.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.attempts, 1)
        self.assertIn("boom", job.last_error)

        job.max_attempts = 1
        job.save(update_fields=["max_attempts"])
        JobRunner.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FAILED)

    def test_unknown_handler_fails(self):
        job = schedule("test.missing")
        JobRunner.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.FAILED)
        self.assertIn("No handler", job.last_error)

    def test_run_due_scheduled_jobs(self):
        ScheduledJob.objects.create(
            name="No-op",
            job="system.noop",
            scheduling="* * * * *",
            last_run=timezone.now() - timedelta(minutes=5),
        )
        created = JobRunner.run_due_scheduled_jobs()
        self.assertEqual(created, 1)
        self.assertTrue(Job.objects.filter(class_name="system.noop").exists())

    def test_run_pending_only_due_jobs(self):
        schedule("system.noop", execute_time=timezone.now() + timedelta(days=1))
        self.assertEqual(JobRunner.run_pending(), 0)
        schedule("system.noop")
        self.assertEqual(JobRunner.run_pending(), 1)

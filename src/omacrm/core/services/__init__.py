from omacrm.core.services.acl import AccessLevel, AclService
from omacrm.core.services.duplicates import (
    DuplicateConflict,
    check_duplicates,
    find_duplicates,
)
from omacrm.core.services.hooks import HookRegistry, hooks
from omacrm.core.services.jobs import JobRegistry, JobRunner, jobs, schedule
from omacrm.core.services.notifications import notify, notify_assignment

# Importing registers the built-in job handlers.
from omacrm.core.services import builtin_jobs  # noqa: E402,F401

__all__ = [
    "AccessLevel",
    "AclService",
    "DuplicateConflict",
    "HookRegistry",
    "JobRegistry",
    "JobRunner",
    "check_duplicates",
    "find_duplicates",
    "hooks",
    "jobs",
    "notify",
    "notify_assignment",
    "schedule",
]

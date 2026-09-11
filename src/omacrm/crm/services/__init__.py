from omacrm.crm.services.email import render_email_template, send_email
from omacrm.crm.services.event_invitations import confirm_attendance, send_invitations
from omacrm.crm.services.lead_convert import LeadConversionService

# Importing registers the knowledge-base and mass-email scheduled jobs.
from omacrm.crm.services import knowledge, mass_email, target_lists  # noqa: E402,F401

__all__ = [
    "LeadConversionService",
    "confirm_attendance",
    "knowledge",
    "mass_email",
    "render_email_template",
    "send_email",
    "send_invitations",
    "target_lists",
]

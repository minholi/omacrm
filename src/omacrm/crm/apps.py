from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "omacrm.crm"
    label = "crm"
    verbose_name = "CRM"

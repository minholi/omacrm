from django.db import migrations
from django.db.models import F


def backfill_email_source(apps, schema_editor):
    EmailTemplate = apps.get_model("crm", "EmailTemplate")
    EmailTemplate.objects.update(source=F("body"), source_format="html")


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0010_emailtemplate_source_emailtemplate_source_format_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_email_source, migrations.RunPython.noop),
    ]

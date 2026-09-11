"""Merge two duplicate records of the same entity type."""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

logger = logging.getLogger(__name__)


@transaction.atomic
def merge_records(master, duplicate, values: dict | None = None) -> dict:
    """Merge ``duplicate`` into ``master``.

    ``values`` maps field names to the value chosen for the master. Related
    records that point to the duplicate are re-pointed to the master where it
    is safe (generic relations and nullable foreign keys); M2M and cascading
    relations are left untouched (those rows belong to the duplicate and are
    soft-deleted with it).
    """

    from omacrm.core.models import Attachment, Email, Note

    model = type(master)
    moved = {"notes": 0, "attachments": 0, "emails": 0, "relations": 0}

    for field_name, value in (values or {}).items():
        setattr(master, field_name, value)

    if values:
        master.save()

    duplicate_ct = ContentType.objects.get_for_model(
        model, for_concrete_model=False
    )
    master_ct = ContentType.objects.get_for_model(master, for_concrete_model=False)

    moved["notes"] += Note.objects.filter(
        parent_type=duplicate_ct, parent_id=duplicate.pk
    ).update(parent_type=master_ct, parent_id=master.pk)
    moved["notes"] += Note.objects.filter(
        related_type=duplicate_ct, related_id=duplicate.pk
    ).update(related_type=master_ct, related_id=master.pk)
    moved["attachments"] += Attachment.objects.filter(
        related_type=duplicate_ct, related_id=duplicate.pk
    ).update(related_type=master_ct, related_id=master.pk)
    moved["emails"] += Email.objects.filter(
        parent_type=duplicate_ct, parent_id=duplicate.pk
    ).update(parent_type=master_ct, parent_id=master.pk)

    for relation in duplicate._meta.related_objects:
        field = relation.field
        if not getattr(field, "many_to_one", False):
            continue
        if not getattr(field, "null", False):
            # Cascading relations belong to the duplicate; leave them.
            continue
        related_model = relation.related_model
        moved["relations"] += related_model.objects.filter(
            **{field.name: duplicate}
        ).update(**{field.name: master})

    duplicate.delete()
    return moved

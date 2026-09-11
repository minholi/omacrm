from django.contrib.contenttypes.models import ContentType

from omacrm.crm.models import TargetListMember


def add_to_target_list(record, target_list, opted_out: bool = False):
    content_type = ContentType.objects.get_for_model(type(record))
    member, _ = TargetListMember.objects.get_or_create(
        target_list=target_list,
        entity_type=content_type,
        entity_id=record.pk,
        defaults={"opted_out": opted_out},
    )
    if member.opted_out != opted_out:
        member.opted_out = opted_out
        member.save(update_fields=["opted_out"])
    return member


def remove_from_target_list(record, target_list) -> int:
    content_type = ContentType.objects.get_for_model(type(record))
    deleted, _ = TargetListMember.objects.filter(
        target_list=target_list,
        entity_type=content_type,
        entity_id=record.pk,
    ).delete()
    return deleted


def set_opt_out(record, target_list, opted_out: bool = True):
    return add_to_target_list(record, target_list, opted_out=opted_out)


def member_records(target_list):
    """Yield ``(member, record)`` pairs for all resolvable members."""

    for member in target_list.members.select_related("entity_type"):
        if member.entity is not None:
            yield member, member.entity

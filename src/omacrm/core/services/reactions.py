"""Emoji reactions on stream notes."""

SUPPORTED_EMOJIS = ["👍", "❤️", "😀", "🎉", "👀"]


def toggle_reaction(note, user, emoji: str = "👍") -> bool:
    """Add the reaction if missing, remove it otherwise.

    Returns ``True`` when the reaction was added, ``False`` when removed.
    """

    from omacrm.core.models import UserReaction

    reaction = UserReaction.objects.filter(note=note, user=user, emoji=emoji)
    if reaction.exists():
        reaction.delete()
        return False
    UserReaction.objects.create(note=note, user=user, emoji=emoji)
    return True


def reaction_users(note, emoji: str):
    from omacrm.core.models import UserReaction

    return UserReaction.objects.filter(note=note, emoji=emoji).select_related("user")

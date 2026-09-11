from django.db.models import Q

from omacrm.core.metadata.registry import registry


class AccessLevel:
    YES = "yes"
    ALL = "all"
    TEAM = "team"
    OWN = "own"
    NO = "no"


LEVEL_ORDER = {
    AccessLevel.NO: 0,
    AccessLevel.OWN: 1,
    AccessLevel.TEAM: 2,
    AccessLevel.ALL: 3,
    AccessLevel.YES: 4,
}

READ_LEVELS = {AccessLevel.YES, AccessLevel.ALL, AccessLevel.TEAM, AccessLevel.OWN}
WRITE_LEVELS = READ_LEVELS


def _highest(levels) -> str:
    if not levels:
        return AccessLevel.NO
    return max(levels, key=lambda level: LEVEL_ORDER.get(level, 0))


class AclService:
    """Role/team based access control.

    Roles (attached to users and teams) define a level per entity type and
    action. Users without any role get full access so a fresh installation
    remains usable; once a user has at least one role, unset scopes are
    denied.
    """

    @classmethod
    def user_roles(cls, user):
        if not user or not user.is_authenticated:
            return []
        roles = list(user.roles.all())
        for team in user.teams.all():
            roles.extend(team.roles.all())
        seen = {}
        for role in roles:
            seen[role.pk] = role
        return list(seen.values())

    @classmethod
    def level(cls, user, entity_type: str, action: str = "read") -> str:
        if not user or not user.is_authenticated:
            return AccessLevel.NO
        if user.is_superuser:
            return AccessLevel.YES
        # Portal users only use the customer portal, never the admin/API ACL.
        if getattr(user, "type", None) == "portal":
            return AccessLevel.NO

        roles = cls.user_roles(user)
        if not roles:
            return cls.default_level(entity_type)

        levels = []
        for role in roles:
            scope = (role.data or {}).get(entity_type) or {}
            level = scope.get(action)
            if level:
                levels.append(level)
        return _highest(levels)

    @classmethod
    def default_level(cls, entity_type: str) -> str:
        if registry.has(entity_type):
            return registry.get(entity_type).acl_default
        return AccessLevel.ALL

    @classmethod
    def check(cls, user, entity_type: str, action: str = "read", record=None) -> bool:
        level = cls.level(user, entity_type, action)
        if level in {AccessLevel.YES, AccessLevel.ALL}:
            return True
        if level == AccessLevel.NO:
            return False
        if record is None:
            return True
        return cls.owns(user, record, level)

    @classmethod
    def owns(cls, user, record, level: str) -> bool:
        if level == AccessLevel.OWN:
            return getattr(record, "assigned_user_id", None) == user.pk or getattr(
                record, "created_by_id", None
            ) == user.pk
        if level == AccessLevel.TEAM:
            if getattr(record, "assigned_user_id", None) == user.pk:
                return True
            team_ids = set(user.teams.values_list("pk", flat=True))
            if not team_ids:
                return False
            return record.teams.filter(pk__in=team_ids).exists()
        return False

    @classmethod
    def scope_queryset(cls, user, entity_type: str, queryset, action: str = "read"):
        level = cls.level(user, entity_type, action)
        if level in {AccessLevel.YES, AccessLevel.ALL}:
            return queryset
        if level == AccessLevel.NO:
            return queryset.none()

        try:
            model = registry.model_for(entity_type)
            field_names = {field.name for field in model._meta.get_fields()}
        except (KeyError, LookupError):
            field_names = set()

        own_conditions = Q()
        if "assigned_user" in field_names:
            own_conditions |= Q(assigned_user=user)
        if "created_by" in field_names:
            own_conditions |= Q(created_by=user)

        if level == AccessLevel.OWN:
            if not own_conditions:
                own_conditions = Q(pk=user.pk)
            return queryset.filter(own_conditions).distinct()

        if level == AccessLevel.TEAM:
            team_conditions = Q(assigned_user=user) if "assigned_user" in field_names else Q()
            if "created_by" in field_names:
                team_conditions |= Q(created_by=user)
            if "teams" in field_names:
                team_conditions |= Q(teams__pk__in=user.teams.values_list("pk", flat=True))
            if not team_conditions:
                team_conditions = Q(pk=user.pk)
            return queryset.filter(team_conditions).distinct()

        return queryset.none()

    @classmethod
    def check_field(cls, user, entity_type: str, field_name: str, action: str = "read") -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        roles = cls.user_roles(user)
        if not roles:
            return True
        levels = []
        for role in roles:
            field_data = (role.field_data or {}).get(entity_type) or {}
            level = field_data.get(field_name)
            if level:
                levels.append(level)
        if not levels:
            return True
        level = _highest(levels)
        return level in {AccessLevel.YES, AccessLevel.ALL}

    @classmethod
    def forbidden_fields(cls, user, entity_type: str) -> set[str]:
        if not user or not user.is_authenticated or user.is_superuser:
            return set()
        fields = registry.fields(entity_type)
        return {
            name
            for name in fields
            if not cls.check_field(user, entity_type, name, "edit")
        }

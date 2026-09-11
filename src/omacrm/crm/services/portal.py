"""Customer-portal access control.

Portal users are regular ``User`` records with ``type == "portal"`` linked to a
``Contact`` (``Contact.portal_user``). Their access is defined by
``PortalRole`` rows; users without roles get sensible defaults.
"""

from django.db.models import Q

DEFAULT_LEVELS = {
    "Case": {"read": "own", "create": "yes", "edit": "own", "delete": "no"},
    "KnowledgeBaseArticle": {"read": "all"},
    "Document": {"read": "own"},
}

LEVEL_ORDER = {"no": 0, "own": 1, "all": 2, "yes": 3}


class PortalAcl:
    @classmethod
    def is_portal_user(cls, user) -> bool:
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "type", None) == "portal"
        )

    @classmethod
    def levels(cls, user) -> dict:
        if not cls.is_portal_user(user):
            return {}

        roles = [role for role in user.portal_roles.all() if role.is_active]
        if not roles:
            return {key: dict(value) for key, value in DEFAULT_LEVELS.items()}

        merged: dict = {}
        for role in roles:
            for entity_type, actions in (role.data or {}).items():
                bucket = merged.setdefault(entity_type, {})
                for action, level in actions.items():
                    if LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER.get(
                        bucket.get(action, "no"), 0
                    ):
                        bucket[action] = level
        return merged

    @classmethod
    def check(cls, user, entity_type: str, action: str = "read", obj=None) -> bool:
        level = cls.levels(user).get(entity_type, {}).get(action)
        if not level or level == "no":
            return False

        if entity_type == "KnowledgeBaseArticle":
            if action == "read" and obj is not None and obj.status != "Published":
                return False
            return True

        if entity_type == "Document":
            if action != "read":
                return False
            if obj is None:
                return level in {"yes", "all", "own"}
            if level in {"yes", "all"}:
                return obj.status == "Active"
            return cls._owns_document(user, obj)

        if action == "create":
            return level in {"yes", "all"}
        if obj is None:
            return level in {"yes", "all", "own"}
        if level in {"yes", "all"}:
            return True
        if level == "own":
            return cls._owns(user, obj)
        return False

    @classmethod
    def _owns(cls, user, obj) -> bool:
        if getattr(obj, "created_by_id", None) == user.pk:
            return True
        contact = getattr(user, "portal_contact", None)
        contact_id = getattr(contact, "pk", None)
        return bool(contact_id and getattr(obj, "contact_id", None) == contact_id)

    @classmethod
    def _owns_document(cls, user, obj) -> bool:
        if obj.status != "Active":
            return False
        contact = getattr(user, "portal_contact", None)
        if contact is None:
            return False
        if obj.contacts.filter(pk=contact.pk).exists():
            return True
        return bool(
            contact.account_id and obj.accounts.filter(pk=contact.account_id).exists()
        )

    @classmethod
    def _documents_for(cls, user, queryset):
        contact = getattr(user, "portal_contact", None)
        if contact is None:
            return queryset.none()
        condition = Q(contacts=contact)
        if contact.account_id:
            condition |= Q(accounts=contact.account_id)
        return queryset.filter(status="Active").filter(condition).distinct()

    @classmethod
    def scope(cls, user, entity_type: str, queryset, action: str = "read"):
        level = cls.levels(user).get(entity_type, {}).get(action)
        if not level or level == "no":
            return queryset.none()
        if entity_type == "Document":
            if action != "read":
                return queryset.none()
            if level in {"yes", "all"}:
                return queryset.filter(status="Active")
            if level == "own":
                return cls._documents_for(user, queryset)
            return queryset.none()
        if level in {"yes", "all"}:
            if entity_type == "KnowledgeBaseArticle" and action == "read":
                return queryset.filter(status="Published")
            return queryset
        if level == "own":
            contact = getattr(user, "portal_contact", None)
            contact_id = getattr(contact, "pk", None)
            condition = Q(created_by=user)
            if contact_id:
                condition |= Q(contact_id=contact_id)
            return queryset.filter(condition).distinct()
        return queryset.none()

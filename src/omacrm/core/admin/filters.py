"""Changelist filters for the current user's stars and follows."""

from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _

from omacrm.core.services import subscriptions


class _SubscriptionListFilter(SimpleListFilter):
    title = ""
    parameter_name = ""
    service_filter = None

    def __init__(self, request, params, model, model_admin):
        self.entity_type = getattr(model_admin, "entity_type", "")
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        return (("1", _("Yes")), ("0", _("No")))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in {"0", "1"} or not self.entity_type:
            return queryset
        return self.service_filter(
            queryset, request.user, self.entity_type, value == "1"
        )


class StarredListFilter(_SubscriptionListFilter):
    title = _("Starred")
    parameter_name = "starred"
    service_filter = staticmethod(subscriptions.filter_starred)


class FollowingListFilter(_SubscriptionListFilter):
    title = _("Following")
    parameter_name = "following"
    service_filter = staticmethod(subscriptions.filter_followed)

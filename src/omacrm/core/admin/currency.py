from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from omacrm.core.models import Currency, CurrencyRate
from omacrm.core.services.jobs import schedule


class CurrencyRateInline(TabularInline):
    model = CurrencyRate
    extra = 0
    fields = ("date", "rate")
    ordering = ("-date",)


@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = ("code", "name", "symbol", "rate", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("updated_at",)
    inlines = (CurrencyRateInline,)
    actions = ("sync_rates",)
    fieldsets = (
        (None, {"fields": ("code", "name", "symbol", "rate", "is_active")}),
        ("System", {"fields": ("updated_at",)}),
    )

    @admin.action(description=_("Sync rates now (enqueue job)"))
    def sync_rates(self, request, queryset):
        schedule("core.sync_currency_rates")
        self.message_user(request, _("Currency rate sync enqueued."))


@admin.register(CurrencyRate)
class CurrencyRateAdmin(ModelAdmin):
    list_display = ("currency", "date", "rate", "created_at")
    list_filter = ("currency",)
    search_fields = ("currency__code", "currency__name")
    date_hierarchy = "date"
    readonly_fields = ("created_at",)

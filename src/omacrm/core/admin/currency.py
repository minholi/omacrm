from django.contrib import admin
from unfold.admin import ModelAdmin

from omacrm.core.models import Currency


@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = ("code", "name", "symbol", "rate", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("updated_at",)
    fieldsets = (
        (None, {"fields": ("code", "name", "symbol", "rate", "is_active")}),
        ("System", {"fields": ("updated_at",)}),
    )

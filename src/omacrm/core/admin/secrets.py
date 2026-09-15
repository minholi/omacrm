from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminPasswordToggleWidget

from omacrm.core.models import AppSecret


class AppSecretForm(forms.ModelForm):
    secret = forms.CharField(
        required=False,
        label=_("Value"),
        widget=UnfoldAdminPasswordToggleWidget,
        help_text=_("Leave blank to keep the current value."),
    )

    class Meta:
        model = AppSecret
        fields = ("name", "description")

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get("secret")
        if raw:
            instance.set_value(raw)
        if commit:
            instance.save()
        return instance


@admin.register(AppSecret)
class AppSecretAdmin(ModelAdmin):
    form = AppSecretForm
    list_display = ("name", "description", "modified_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "modified_at")
    fieldsets = (
        (None, {"fields": ("name", "secret", "description")}),
        (_("System"), {"fields": ("created_at", "modified_at")}),
    )

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from hijack.contrib.admin import HijackUserAdminMixin
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm

from omacrm.core.admin.base import AclAdminMixin, MetadataModelAdmin
from omacrm.core.forms import CoreUserChangeForm, CoreUserCreationForm
from omacrm.core.models import Preferences, Role, Team, TeamUser, User


@admin.register(User)
class UserAdmin(HijackUserAdminMixin, AclAdminMixin, BaseUserAdmin, ModelAdmin):
    entity_type = "User"
    add_form = CoreUserCreationForm
    form = CoreUserChangeForm
    change_password_form = AdminPasswordChangeForm
    list_display = (
        "user_name",
        "name",
        "email",
        "type",
        "is_active",
        "is_staff",
        "last_access",
    )
    list_filter = ("type", "is_active", "is_staff")
    search_fields = ("user_name", "first_name", "last_name", "email")
    ordering = ("user_name",)
    filter_horizontal = ("roles", "user_permissions")
    readonly_fields = ("last_access",)
    fieldsets = (
        (None, {"fields": ("user_name", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "title",
                    "phone_number",
                    "avatar",
                )
            },
        ),
        (
            _("Access"),
            {
                "fields": (
                    "type",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "default_team",
                    "roles",
                )
            },
        ),
        (
            _("Important dates"),
            {"fields": ("last_login", "last_access", "date_joined")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "user_name",
                    "first_name",
                    "last_name",
                    "email",
                    "password1",
                    "password2",
                    "type",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


class TeamUserInline(TabularInline):
    model = TeamUser
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "position")


@admin.register(Team)
class TeamAdmin(MetadataModelAdmin):
    entity_type = "Team"
    search_fields = ("name", "description")
    inlines = (TeamUserInline,)
    autocomplete_fields = ("roles",)


@admin.register(Role)
class RoleAdmin(MetadataModelAdmin):
    entity_type = "Role"
    search_fields = ("name", "description")
    list_display = ("name", "description", "access_matrix", "created_at")

    @admin.display(description=_("Access"))
    def access_matrix(self, obj):
        from django.urls import reverse
        from django.utils.safestring import mark_safe

        url = reverse("role_acl_editor", args=[obj.pk])
        return mark_safe(
            f'<a class="text-primary-600 dark:text-primary-500" href="{url}">'
            f'{_("Edit access")}</a>'
        )


@admin.register(TeamUser)
class TeamUserAdmin(ModelAdmin):
    list_display = ("team", "user", "role", "position")
    list_filter = ("team",)
    search_fields = ("team__name", "user__user_name")
    autocomplete_fields = ("team", "user")


@admin.register(Preferences)
class PreferencesAdmin(ModelAdmin):
    list_display = ("user", "language", "time_zone", "default_currency")
    search_fields = ("user__user_name",)
    autocomplete_fields = ("user",)

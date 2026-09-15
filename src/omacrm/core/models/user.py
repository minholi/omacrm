from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from omacrm.core.models.base import CustomDataMixin


class Role(CustomDataMixin, models.Model):
    """Role-based access data.

    ``data`` maps scope names to action levels, e.g.
    ``{"Account": {"read": "team", "edit": "own"}}``.
    ``field_data`` maps scope names to per-field levels.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    field_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(CustomDataMixin, models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    roles = models.ManyToManyField(Role, blank=True, related_name="teams")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, user_name, email, password, **extra_fields):
        if not user_name:
            raise ValueError("The user name must be set")
        user = self.model(user_name=user_name, email=email or "", **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, user_name, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(user_name, email, password, **extra_fields)

    def create_superuser(self, user_name, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("type", User.Type.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(user_name, email, password, **extra_fields)


class User(CustomDataMixin, AbstractBaseUser, PermissionsMixin):
    class Type(models.TextChoices):
        REGULAR = "regular", "Regular"
        ADMIN = "admin", "Admin"
        PORTAL = "portal", "Portal"
        SYSTEM = "system", "System"
        API = "api", "API"

    user_name = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=50, blank=True, default="")
    last_name = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.REGULAR)
    title = models.CharField(max_length=100, blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    default_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    teams = models.ManyToManyField(
        Team,
        through="core.TeamUser",
        through_fields=("user", "team"),
        blank=True,
        related_name="users",
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="users")
    portal_roles = models.ManyToManyField(
        "core.PortalRole", blank=True, related_name="users"
    )
    api_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    last_access = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "user_name"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["user_name"]

    def __str__(self):
        return self.user_name

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.user_name

    def get_short_name(self):
        return self.first_name or self.user_name

    @property
    def name(self):
        return self.get_full_name()

    # -- Unfold avatar integration -----------------------------------------

    @property
    def avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except ValueError:
                return ""
        return ""

    @property
    def avatar_badge_variant(self):
        return "primary" if self.pk else None

    @property
    def avatar_badge_count(self):
        if not self.pk:
            return None
        from omacrm.core.models import Notification

        count = Notification.objects.filter(user=self, read=False).count()
        return count or None

    @property
    def avatar_badge_url(self):
        if not self.pk:
            return None
        from django.urls import reverse

        return reverse("admin:core_notification_changelist")


class TeamUser(models.Model):
    """Membership of a user in a team, with optional team-specific role."""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=100, blank=True, default="")
    position = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        unique_together = [("team", "user")]
        ordering = ["team__name", "user__user_name"]

    def __str__(self):
        return f"{self.user} @ {self.team}"


class Preferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")
    time_zone = models.CharField(max_length=64, blank=True, default="")
    date_format = models.CharField(max_length=32, blank=True, default="")
    time_format = models.CharField(max_length=32, blank=True, default="")
    language = models.CharField(max_length=10, blank=True, default="en")
    theme = models.CharField(max_length=32, blank=True, default="")
    default_currency = models.CharField(max_length=3, blank=True, default="")
    notifications_config = models.JSONField(default=dict, blank=True)
    auto_follow_entity_types = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "preferences"

    def __str__(self):
        return f"Preferences of {self.user}"

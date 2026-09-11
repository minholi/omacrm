from unfold.forms import UserChangeForm, UserCreationForm

from omacrm.core.models import User


class CoreUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "user_name",
            "first_name",
            "last_name",
            "email",
            "type",
            "is_active",
            "is_staff",
            "is_superuser",
        )


class CoreUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

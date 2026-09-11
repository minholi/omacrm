from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions

from omacrm.core.models import User


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate with a user's API key sent in the ``X-Api-Key`` header."""

    keyword = "X-Api-Key"

    def authenticate(self, request):
        key = request.headers.get(self.keyword) or request.META.get("HTTP_X_API_KEY")
        if not key:
            return None

        user = User.objects.filter(api_key=key, is_active=True).first()
        if user is None:
            raise exceptions.AuthenticationFailed(_("Invalid API key."))
        return (user, None)

    def authenticate_header(self, request):
        return self.keyword

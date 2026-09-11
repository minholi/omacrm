from omacrm.core.services.context import set_current_user


class CurrentUserMiddleware:
    """Expose the request user to services (stream notes, audit columns)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            set_current_user(request.user)
        response = self.get_response(request)
        set_current_user(None)
        return response

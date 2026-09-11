import contextvars

_current_user = contextvars.ContextVar("omacrm_current_user", default=None)


def set_current_user(user):
    return _current_user.set(user)


def get_current_user():
    return _current_user.get()

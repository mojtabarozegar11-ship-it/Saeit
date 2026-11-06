"""Limit the account-backed game API to the MojPlayWin host.

Both Zomorod and MojPlayWin share one Django codebase, not one game namespace.
The guard runs on every game URL before a read or mutation is dispatched.
"""
from functools import wraps

from django.conf import settings
from django.http import Http404


MOJPLAYWIN_HOSTS = frozenset({"mojplaywin.com", "www.mojplaywin.com"})
DEVELOPMENT_HOSTS = frozenset({"testserver", "localhost", "127.0.0.1"})


def mojplaywin_only(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        host = request.get_host().split(":", 1)[0].lower()
        if host not in MOJPLAYWIN_HOSTS and not (
            settings.DEBUG and host in DEVELOPMENT_HOSTS
        ):
            raise Http404("not_found")
        return view(request, *args, **kwargs)

    return guarded

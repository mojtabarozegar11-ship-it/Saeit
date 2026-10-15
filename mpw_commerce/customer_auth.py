"""MojPlayWin-only customer access required by existing paid-download flow.

TLS and domain restricted. Django password validation, CSRF and salted hashes
are used; no payment actions, wallets or staff authentication changes.
"""
import hashlib

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


class CustomerSignupForm(UserCreationForm):
    """Enforce a hard password length floor even if host validators are missing."""

    def clean_password2(self):
        # Django 5.2 UserCreationForm delegates pair matching to SetPasswordMixin.
        # Do not rely on a clean_password2 superclass method.
        password = self.cleaned_data.get("password2") or ""
        if len(password) < 12 or len(password) > 128:
            raise ValidationError("Choose a password between 12 and 128 characters.")
        return password


def _check_host(request):
    if not request.is_secure() or request.get_host().split(":")[0].lower() not in HOSTS:
        raise Http404("MojPlayWin HTTPS required")


def _too_many(request, prefix, limit):
    if request.method != "POST":
        return False
    address = request.META.get("REMOTE_ADDR", "")[:80]
    digest = hashlib.sha256(address.encode("utf-8")).hexdigest()
    key = "mpw-buyer-" + prefix + "-" + digest
    if cache.add(key, 1, timeout=900):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, timeout=900)
        return False


class CustomerLogin(LoginView):
    template_name = "mpw_commerce/customer_login.html"
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        _check_host(request)
        if _too_many(request, "login", 20):
            return HttpResponse("Too many attempts. Try later.", status=429)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return "/commerce/my-purchases/"


class CustomerLogout(LogoutView):
    next_page = "/accounts/login/"

    def dispatch(self, request, *args, **kwargs):
        _check_host(request)
        return super().dispatch(request, *args, **kwargs)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def customer_register(request):
    _check_host(request)
    if _too_many(request, "register", 6):
        return HttpResponse("Too many registrations. Try later.", status=429)
    if request.user.is_authenticated:
        return redirect("/commerce/my-purchases/")
    form = CustomerSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("/commerce/my-purchases/")
    return render(request, "mpw_commerce/customer_register.html", {"form": form})

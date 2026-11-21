"""Customer-only, passwordless authentication; off until verified mail configuration."""
from hashlib import sha256
from django.conf import settings
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from .simulation_identity import issue_challenge, consume_challenge, is_verified_simulation_user

def available(request):
    return (request.get_host().lower() == "mojplaywin.com" and request.is_secure()
            and getattr(settings, "MPW_SIMULATION_IDENTITY_ENABLED", False) is True
            and bool(getattr(settings, "MPW_SIMULATION_FROM_EMAIL", "")))

@never_cache
@csrf_protect
@require_http_methods(["GET", "HEAD", "POST"])
def simulation_login(request):
    if not available(request):
        raise Http404
    if request.user.is_authenticated:
        if is_verified_simulation_user(request.user):
            return redirect("moj_prop_landing")
        return HttpResponse("Sign out of your other account before signing in here.", status=403)
    message = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "request":
            ip = request.META.get("REMOTE_ADDR", "")
            if not ip:
                return HttpResponse("Unavailable", status=503)
            key = "mojprop:login:" + sha256(ip.encode()).hexdigest()
            try:
                if not cache.add(key, 1, timeout=600) and cache.incr(key) > 5:
                    return HttpResponse("Please retry later", status=429)
            except Exception:
                return HttpResponse("Unavailable", status=503)
            try:
                issued = issue_challenge(request.POST.get("email", ""))
            except ValidationError:
                issued = None
            if issued:
                identifier, code = issued
                try:
                    sent = send_mail("Your Moj Prop sign-in code",
                        "Your sign-in code is " + code + ". It expires in 10 minutes. Never share it.",
                        settings.MPW_SIMULATION_FROM_EMAIL, [request.POST["email"]],
                        fail_silently=False)
                except Exception:
                    sent = 0
                if sent == 1:
                    request.session["mojprop_challenge"] = identifier
                else:
                    return HttpResponse("Email delivery unavailable. Please retry later.", status=503)
            message = "If your request is eligible, use the code sent to your email."
        elif action == "confirm":
            user = consume_challenge(request.session.get("mojprop_challenge"), request.POST.get("code", ""))
            if user is not None:
                request.session.pop("mojprop_challenge", None)
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("moj_prop_landing")
            message = "Invalid or expired code. Request a new code if necessary."
        else:
            return HttpResponse("Invalid request", status=400)
    return render(request, "mojplaywin/moj_prop_simulation_login.html", {"message": message})

@never_cache
@require_POST
@csrf_protect
def simulation_logout(request):
    if not available(request) or not is_verified_simulation_user(request.user):
        raise Http404
    logout(request)
    return redirect("moj_prop_landing")

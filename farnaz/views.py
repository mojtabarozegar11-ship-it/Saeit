from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import FarnazInquiry, FarnazOffer, FarnazProject, FarnazService


@require_GET
def home(request):
    return render(request, "farnaz/index.html", {
        "services": FarnazService.objects.filter(active=True),
        "projects": FarnazProject.objects.filter(active=True),
        "offers": FarnazOffer.objects.filter(active=True),
    })


@require_POST
def submit_inquiry(request):
    if request.POST.get("website", "").strip():
        return redirect("/farnaz/?sent=1#contact")
    name = request.POST.get("name", "").strip()[:120]
    phone = request.POST.get("phone", "").strip()[:40]
    email = request.POST.get("email", "").strip()[:254]
    message = request.POST.get("message", "").strip()[:3000]
    category = request.POST.get("category", "").strip()
    consent = request.POST.get("consent") == "on"
    categories = {value for value, _label in FarnazInquiry.Category.choices}
    if not (name and phone and message and consent and category in categories):
        messages.error(request, "Please complete your name, phone, topic, project brief and privacy consent.")
        return redirect("/farnaz/#contact")
    FarnazInquiry.objects.create(
        name=name, phone=phone, email=email, message=message,
        category=category, consent=consent,
    )
    return redirect("/farnaz/?sent=1#contact")

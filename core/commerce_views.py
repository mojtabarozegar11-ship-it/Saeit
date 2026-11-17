from django.shortcuts import render
from .models import Product
from .procurement_notices import get_public_procurement_notices


def store_home(request):
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from .mojplaywin_views import store
        return store(request)
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    # Public, non-binding purchase RFQs are separate from staff-only PrivateAuction records.
    notices, policy = get_public_procurement_notices()
    return render(request, "core/auctions.html", {
        "auctions": [],
        "supply_notices": notices["supply"],
        "equipment_notices": notices["equipment"],
        "procurement_policy": policy,
    })

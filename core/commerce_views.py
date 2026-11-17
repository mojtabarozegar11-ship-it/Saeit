from django.shortcuts import render
from .models import Product


def store_home(request):
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from .mojplaywin_views import store
        return store(request)
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    return render(request, "core/auctions.html", {"auctions": []})


def auction_346(request):
    """Public read-only research procurement notice, never a live bidding endpoint."""
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from django.http import Http404
        raise Http404
    return render(request, "core/auction_346.html")

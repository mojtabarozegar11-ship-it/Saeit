from django.shortcuts import render
from .models import Product


def store_home(request):
    if request.get_host == "mojplaywin.com" or request.get_host == "www.mojplaywin.com":
        from .mojplaywin_views import store
        return store(request)
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    return render(request, "core/auctions.html", {"auctions": []})

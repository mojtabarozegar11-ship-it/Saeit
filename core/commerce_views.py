from django.shortcuts import render
from .models import Product
from .factory_storefront import presentation


def store_home(request):
    products = list(Product.objects.filter(active=True).order_by("-id"))
    host = request.get_host().split(":")[0].lower()
    if host in ("mojplaywin.com", "www.mojplaywin.com"):
        factory_cards, regular_products = presentation(products)
        return render(request, "core/mojplaywin_factory_store.html", {
            "factory_cards": factory_cards,
            "other_products": regular_products,
        })
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    return render(request, "core/auctions.html", {"auctions": []})

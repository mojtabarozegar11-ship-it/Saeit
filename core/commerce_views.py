from django.shortcuts import render
from .models import Product


def store_home(request):
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    return render(request, "core/auctions.html", {"auctions": []})

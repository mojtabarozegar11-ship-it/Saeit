from django.shortcuts import render
from .models import Product


def store_home(request):
    # Use the same strict canonical-host predicate as MojPlayWin pages.
    # The public /store/ URL is routed here, not through branded_store_dispatch.
    from .mojplaywin_views import _is_mojplaywin, store
    if _is_mojplaywin(request):
        return store(request)
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    return render(request, "core/auctions.html", {"auctions": []})

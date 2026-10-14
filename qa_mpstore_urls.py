"""Test-only miniature router mirroring active cPanel branded_store dispatch.

Production module core.brand_views is installed only on cPanel and MUST NOT
be overwritten from this source repository. This is NOT production URLConf.
"""
from types import SimpleNamespace
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from core.models import Product
from core.commerce_views import store_home
from core.brand_store_integration import safe_brand_store_context


def qa_branded_store(request):
    host = request.get_host().split(":")[0].lower().rstrip(".")
    if host in ("mojplaywin.com", "www.mojplaywin.com"):
        brand = SimpleNamespace(code="mojplaywin", name="MojPlayWin")
        products = list(Product.objects.filter(active=True).order_by("-id"))
        context = safe_brand_store_context(brand, products)
        return render(request, "core/mojplaywin_factory_store.html", context)
    return store_home(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("store/", qa_branded_store, name="store"),
]

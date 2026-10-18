"""Main MojPlayWin-only web engineering content.

No writes, products, checkout, wallet operations, admin changes or shared
subsite routing. This view is staged in the preview URLConf pending a verified
safe production domain-routing solution.
"""
from django.http import Http404
from django.shortcuts import render


def web_engineering(request):
    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"}:
        raise Http404("This page belongs only to the main MojPlayWin website")
    return render(request, "mojplaywin/web_engineering.html")

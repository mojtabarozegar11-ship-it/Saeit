"""Read-only public newsletter routes restricted to MojPlayWin's own hostname."""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render

from .mojplaywin_newsroom import CATEGORIES, Newsroom, is_mojplaywin, private_db_path


def only_mojplaywin(request):
    if not is_mojplaywin(request.get_host()):
        raise Http404


def homepage(request):
    only_mojplaywin(request)
    category = request.GET.get("category", "")
    if category not in CATEGORIES:
        category = ""
    store = Newsroom(private_db_path())
    return render(request, "mojplaywin/newsletter.html", {
        "articles": store.list_published(category),
        "category": category,
        "categories": sorted(CATEGORIES),
    })


def archive(request):
    return homepage(request)


def detail(request, slug):
    only_mojplaywin(request)
    story = Newsroom(private_db_path()).get_published(slug)
    if story is None:
        raise Http404
    story["keywords"] = json.loads(story["keywords"])
    return render(request, "mojplaywin/newsletter_detail.html", {"story": story})


def staff_dashboard(request):
    only_mojplaywin(request)
    return staff_member_required(_staff_dashboard)(request)


def _staff_dashboard(request):
    return render(request, "mojplaywin/newsletter_staff.html", {
        "stats": Newsroom(private_db_path()).stats(),
        "minimum_quality": 90,
    })

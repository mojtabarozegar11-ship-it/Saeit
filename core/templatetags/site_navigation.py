from django import template

from core.models import SiteNavigationItem


register = template.Library()


def _is_current(path, prefix):
    if not prefix:
        return False
    if prefix == "/":
        return path == "/"
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


@register.simple_tag
def site_navigation(area, path="/"):
    rows = SiteNavigationItem.objects.filter(area=area, is_active=True).order_by(
        "sort_order", "id"
    )
    return [
        {
            "title": row.title,
            "url": row.url,
            "is_current": any(_is_current(path, prefix) for prefix in row.active_prefixes),
        }
        for row in rows
    ]

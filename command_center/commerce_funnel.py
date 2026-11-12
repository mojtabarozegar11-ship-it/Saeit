from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone

from core.models import CommerceFunnelEvent


@staff_member_required
def commerce_funnel_api(request):
    """Read-only funnel summary for staff; never exposes visitor identifiers."""
    since = timezone.now() - timedelta(days=30)
    rows = CommerceFunnelEvent.objects.filter(created_at__gte=since)
    by_event = {
        event: rows.filter(event_name=event).count()
        for event, _label in CommerceFunnelEvent.EVENT_CHOICES
    }
    products = []
    for product_id in rows.filter(product_id__isnull=False).values_list("product_id", flat=True).distinct():
        product_rows = rows.filter(product_id=product_id)
        product = product_rows.select_related("product").first().product
        products.append({
            "product_id": product_id,
            "title": product.title,
            "events": {
                event: product_rows.filter(event_name=event).count()
                for event, _label in CommerceFunnelEvent.EVENT_CHOICES
            },
        })
    return JsonResponse({
        "window_days": 30,
        "read_only": True,
        "events": by_event,
        "products": products,
    })

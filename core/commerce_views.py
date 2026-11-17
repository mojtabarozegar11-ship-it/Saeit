from django.shortcuts import render
from .models import Product
from .procurement_notices import get_public_procurement_notices


def store_home(request):
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from .mojplaywin_views import store
        return store(request)
    products = Product.objects.filter(active=True).order_by("-id")
    return render(request, "core/store.html", {"products": products})


def auctions_home(request):
    # Public RFQ codes are immutable identifiers, NOT public ad serial numbers.
    # Do not display these 72 announcements until ALL real serials are reserved
    # strictly after the previous official advertisement high-watermark.
    from command_center.models import PublicProcurementNumber

    grouped, policy = get_public_procurement_notices()
    all_notices = grouped["supply"] + grouped["equipment"]
    serials = dict(
        PublicProcurementNumber.objects.filter(
            notice_key__in=[notice["id"] for notice in all_notices]
        ).values_list("notice_key", "serial_number")
    )
    # Enforce contiguous, ordered blocks: 36 supply ads followed by 36 equipment ads.
    # An incomplete or out-of-order numbering ledger cannot make the public page live.
    ready = len(serials) == len(all_notices) and len(set(serials.values())) == len(all_notices)
    if ready:
        numbers = [serials[item["id"]] for item in all_notices]
        ready = numbers == list(range(numbers[0], numbers[0] + len(numbers)))
    if ready:
        supply = [dict(item, public_number=serials[item["id"]]) for item in grouped["supply"]]
        equipment = [dict(item, public_number=serials[item["id"]]) for item in grouped["equipment"]]
    else:
        # Fail closed if the ledger is incomplete, to avoid public numbering conflicts.
        supply, equipment = [], []

    return render(request, "core/auctions.html", {
        "auctions": [],
        "supply_notices": supply,
        "equipment_notices": equipment,
        "procurement_policy": policy,
        "numbering_ready": ready,
    })

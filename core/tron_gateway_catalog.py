"""Bounded eligibility-first pagination for the native-TRX product catalogue.

A published-but-ineligible product is never counted as a sellable result.
No DB, network, wallet, email or payment operation is performed here.
"""

PAGE_SIZE = 50
MAX_CATALOG_PAGE = 100
MAX_CATALOG_SCANNED = 5000


class CatalogueScanLimit(ValueError):
    """Do not claim catalogue completeness beyond a bounded audit."""


def paginate_eligible(candidates, approve, *, page):
    """Return (items, has_more) using *eligible* offsets, not raw DB offsets.

    The caller supplies active products in stable, ascending primary-key order.
    `approve(product)` returns a display value or None for an unapproved item.
    An extra eligible item, not an arbitrary active row, proves has_more.
    """
    if type(page) is not int or not 1 <= page <= MAX_CATALOG_PAGE:
        raise ValueError("Invalid catalogue page")
    start = (page - 1) * PAGE_SIZE
    items = []
    eligible_seen = 0
    for scanned, candidate in enumerate(candidates, start=1):
        if scanned > MAX_CATALOG_SCANNED:
            raise CatalogueScanLimit("Catalogue scan exceeds safe bound")
        item = approve(candidate)
        if item is None:
            continue
        eligible_seen += 1
        if eligible_seen <= start:
            continue
        if len(items) == PAGE_SIZE:
            return items, True
        items.append(item)
    return items, False

"""Prioritize real commerce-funnel investigation from internal event counters.

Funnel counters are telemetry events, not unique customers, provider receipts,
delivered orders or verified cash. No conversion rate or income is inferred.
"""

EVENT_NAMES = (
    "view_store", "view_item", "begin_checkout", "invoice_created",
    "payment_confirmed", "delivery_success", "delivery_failure",
)


def decide_funnel_followup(event_counts, sellable_offers):
    """Return one safe next diagnostic step, never an external action."""
    if type(sellable_offers) is not int or sellable_offers < 0:
        raise ValueError("sellable_offers_must_be_nonnegative_integer")
    if not isinstance(event_counts, dict):
        raise ValueError("event_counts_must_be_dictionary")
    counts = {}
    for name in EVENT_NAMES:
        count = event_counts.get(name)
        if type(count) is not int or count < 0:
            raise ValueError(f"{name}_must_be_nonnegative_integer")
        counts[name] = count

    if counts["delivery_failure"]:
        next_action, reason = "inspect_delivery_failures", "logged_delivery_failures"
    elif counts["payment_confirmed"] and not counts["delivery_success"]:
        next_action, reason = "inspect_payment_to_delivery_path", "payment_event_without_delivery_event_in_period"
    elif counts["begin_checkout"] and not counts["invoice_created"]:
        next_action, reason = "inspect_checkout_to_invoice_path", "checkout_events_without_invoice_event_in_period"
    elif counts["invoice_created"] and not counts["payment_confirmed"]:
        next_action, reason = "inspect_invoice_to_payment_path", "invoice_events_without_payment_event_in_period"
    elif sellable_offers == 0:
        next_action, reason = "prepare_verified_sellable_offer", "no_active_positive_price_offer"
    elif counts["view_store"] == 0 and counts["view_item"] == 0:
        next_action, reason = "prepare_free_customer_acquisition", "no_recorded_store_or_product_views"
    elif not counts["begin_checkout"]:
        next_action, reason = "inspect_product_to_checkout_path", "views_without_checkout_events_in_period"
    else:
        next_action, reason = "inspect_external_settlement_and_fulfillment", "funnel_has_progress_but_cash_not_verified"

    return {
        "next_diagnostic": next_action,
        "reason": reason,
        "event_counts": counts,
        "sellable_offers": sellable_offers,
        "internal_event_counts_only": True,
        "unique_customers_proven": False,
        "sales_settlement_verified": False,
        "external_write_permitted": False,
        "purchase_permitted": False,
    }

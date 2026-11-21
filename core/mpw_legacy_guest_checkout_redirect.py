"""Narrow, side-effect-free repair for three legacy MojPlayWin guest checkout links.

Old URLs were public on prior releases and currently return HTTP 404. This
module does not place orders, access Django models, inspect customers, set
cookies, follow attacker query parameters, or modify payment state.
"""
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

# Three SKUs independently verified as public on the current /store/ landing.
# No wildcard open redirect: other IDs keep their existing 404.
PUBLIC_GUEST_SKUS = frozenset((72, 225, 879))


@never_cache
@require_safe
def legacy_guest_checkout(request, product_id: int):
    if product_id not in PUBLIC_GUEST_SKUS:
        raise Http404("Unknown public product")
    # Deliberately drop untrusted legacy URL query parameters (including
    # tokens and potential PII); the new checkout obtains a fresh CSRF token.
    target = reverse("mpw_trx_checkout", kwargs={"product_id": product_id})
    return HttpResponseRedirect(target)

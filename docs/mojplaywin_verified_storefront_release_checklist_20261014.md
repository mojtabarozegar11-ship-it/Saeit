# MojPlayWin factory storefront — targeted integration release checklist

**2026-10-14. Status: CI PASS; NOT DEPLOYED TO PRODUCTION.**

The active `/store/` route uses `core.brand_views.branded_store` and the existing `brands/mojplaywin/store.html`, **not** `core.commerce_views.store_home`. The live brand callback source was observed in a prior read-only host audit:

```python
def branded_store(request):
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin":
        raise Http404
    try:
        products=list(Product.objects.filter(active=True).order_by("-id"))
    except Exception:
        products=[]
    return render(request,"brands/mojplaywin/store.html",{"brand":brand,"products":products})
```

This shape must still match before any change. Never overwrite the live `config/urls.py`, `core/brand_views.py` as a whole, or the active branded store template with an old source-control copy.

## What can be installed through an authorized change window

Stage precisely three new, separately code-reviewed files under the active Django app in `/home/zomorod2/Saeit-staging/`:

- `core/factory_storefront.py`: selects only explicitly approved factory products with verified payment and delivery gates; no invented former price.
- `core/brand_store_integration.py`: MojPlayWin-specific catalog context adapter and preservation of ordinary products.
- `core/templates/core/includes/mpw_verified_factory_cards.html`: compact add-on HTML partial.

Then generate a **reviewable candidate**, do not overwrite production:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/mpw_branded_store_targeted_patch.py \
  --source /home/zomorod2/Saeit-staging/core/brand_views.py \
  --output /home/zomorod2/.mpw-private-release/brand_views.candidate.py
```

The generator fails closed if the installed `branded_store` AST no longer matches the verified baseline. It changes just that function in a candidate file. If the generated candidate is unexpectedly different, **stop** rather than adjusting guards by hand.

## Mandatory release preflight (not yet satisfied by this chat)

1. Use an **authorized** cPanel/VPS deployment channel. Previous remote desktop request was denied and repeated workflow creation was blocked; do not bypass those controls.
2. Establish a fresh non-web 0600 backup of the active `core/brand_views.py` and a rollback path, plus a fresh recoverable database backup before any *product activation*.
3. Verify the candidate source and installed helper/template are syntax-valid, all expected Django imports resolve, `DEBUG=False`, and the live-brand callback still matches the checked AST.
4. In private shadow, render the exact **existing branded** MojPlayWin page, test HTML fragment insertion using a staff-safe candidate, and verify that other brands are unaffected. The HTML insertion is **fail soft**: if no safe marker exists, return the existing page rather than throwing HTTP 500.
5. Only after testing, apply the scoped function patch atomically, restart Passenger, then perform real HTTP smoke of `/`, `/admin/`, `/staff/`, `/staff/command-center/`, `/store/`, and the verified free ZIP; roll back automatically if site health changes.
6. The **existing Farm Enterprise Free Edition** page and ZIP are already public, but the native catalog product #131 was previously inactive. Native publication must use the separately verified, explicitly approved factory free-publisher gate — its dry-run passed. Do not set `active=True` by an uncontrolled SQL update.
7. Water Budget product #147 has proposed and stored launch price **USD $0.99** (90% below assessed value USD $9.90), but must remain inactive until a real secured mainnet payment flow, fulfillment, copyright/license, service/quality and buyer access are independently validated. Never advertise an unsubstantiated previous $9.90 sales price.

## Automated tests already passing

**23/23** isolated Django and targeted patch tests: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38601941777. These tests specifically cover unchanged non-MojPlayWin brands, free product gating, refusal of unverified paid checkout, exact-source AST checks, HTML insertion into a brand page and fail-soft preservation when HTML has no safe insertion marker.

Prior cPanel private-shadow compatibility tests: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38596724509. Note: those were shadow tests and **not** a release.

## Operational boundary

This document is not a claim of a completed live deployment. No production file, database row, paid checkout switch, or factory loop was changed by the current scoped patch development and CI.

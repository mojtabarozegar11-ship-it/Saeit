# MojPlayWin factory listings — compatibility with actual cPanel route

Verified read-only, 2026-10-14:

- `/store/` is an active `config.urls` *lambda* that dispatches `branded_store(request)` when `brand_for_request(request)` resolves a brand; otherwise it uses `store_home(request)`.
- The live `core.brand_views.branded_store` first checks that `brand.code == 'mojplaywin'`, then queries `core.Product.objects.filter(active=True)` and renders `brands/mojplaywin/store.html`.
- The active route is **not** the repository's plain `core.commerce_views.store_home`. The old branch-specific `core/commerce_views.py` override has been reverted to prevent a misleading / risky production patch.
- These facts were verified through pinned SSH from GitHub Actions, **read-only**:
  - https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38597450356
  - https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38597686801
  - https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38597840863

## Safe integration, NOT deployed

1. Use `core.factory_storefront.presentation` and `core.brand_store_integration.safe_brand_store_context` to filter factory products before they reach the actual MojPlayWin branded template. Existing active nonfactory products remain under `products`; release-approved factory listings are separately placed into `factory_cards`.
2. Integrate with the live `core.brand_views.branded_store` by a **surgical** edit after verifying exact deployed code and a same-host 0600 backup, keeping the existing brand identity validation and `/store/` URL dispatcher. Sketch, not deployable by copy/paste without on-host diff:

   ```python
   from core.brand_store_integration import safe_brand_store_context
   # inside the existing branded_store() after product retrieval:
   context = safe_brand_store_context(brand, products)
   return render(request, "brands/mojplaywin/store.html", context)
   ```

3. Do not overwrite the existing `brands/mojplaywin/store.html`. After auditing its actual origin, add a **small included factory-cards section** using `factory_cards` to preserve all existing brand layout and established product sections.
4. Both factory records (farm #131 at USD 0, water budget #147 at USD 0.99) remain inactive until permissioned publication. The installed free toolkit publisher passed a real Django **dry run only** with product 131. Paid Water Budget must stay hidden pending actual mainnet/payment and delivery validation. A private export must not be mistaken for a successful public sale.
5. Verify `/admin/`, `/staff/`, `/staff/command-center/`, `/store/`, and `/factory-releases/farm-enterprise-economics-v1/` after any controlled deployment. Preserve a tested rollback and never copy full `config/urls.py`, `core/brand_views.py`, or unrelated Django settings from the older GitHub snapshot over the active cPanel files.

## Completed tests

- The revised isolated brand-routing simulation and factory-gate module passed **10/10 tests**, covering free access, strict paid checkout gating, spoofed URLs, false former prices, regular products, and non-MojPlayWin brand rejection:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38598525530
- Prior private cPanel template shadow tests passed, but they did not use the real installed branded-store template:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38596724509

**Production status:** no new storefront deployment, no product activation, no payment enablement, and no changes to live databases in this branch. Further attempts to create on-host audit / publication workflows were blocked by tool security controls, so the remaining controlled publication step needs an approved execution path. Do not work around those controls.

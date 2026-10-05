# Activation: exact remaining gates

## 1. Current blockers

- `ZARINPAL_MERCHANT_ID`: absent in reviewed production environment; obtain a legitimate approved merchant for the actual seller, domain and permitted product. Provider KYC and any applicable business requirements belong to the human owner.
- `SECRET_KEY`: the production project `.env` exists with mode 0600 and Django resolves a weak/short value. The earlier probe looked for `SECRET_KEY`, the wrong name. Verify the effective Passenger Application Manager value without displaying it. Owner approval is required before replacing a key because active sessions will be invalidated.
- Seller identity, public support contact, refund/support terms and ability to meet the proposed support target need owner approval.
- Real sandbox/merchant tests, physical mobile use, browser UX and independent security review are incomplete.
- Production deployment itself requires explicit owner approval under the current mission.

## 2. Server-only configuration

Configure these through the existing protected environment loader, never the frontend:

| Key | Required value/action |
|---|---|
| `SECRET_KEY` | Strong unique secret; approve rotation and session effects |
| `ZARINPAL_MERCHANT_ID` | Actual approved merchant identifier |
| `ZARINPAL_SANDBOX` | `0` for live. Live checkout deliberately refuses sandbox mode |
| `ZM_COSTKIT_SELLER` | Verified legal seller display identity |
| `ZM_COSTKIT_SUPPORT_EMAIL` | Actual monitored address; no assumed mailbox |
| `ZM_COSTKIT_PRICE_IRR` | Proposed `1490000` IRR = `149000` toman; owner may change |
| `ZM_COSTKIT_APPROVED_PRICE_IRR` | Exact approved IRR price; must match above |
| `ZM_COSTKIT_TERMS_APPROVED` | `costkit-1.0-20261005` after legal/business review |
| `ZM_COSTKIT_RELEASE_SHA256` | Exact SHA-256 of deterministic product ZIP approved by owner |
| `ZM_COSTKIT_LIVE` | Keep absent/`0` until all checks and explicit launch approval; `1` enables checkout |
| `ZM_COSTKIT_DATA_DIR` | Private persistent directory, e.g. `/home/zomorod2/Saeit/var/moj/costkit` |

### Django secret setup — owner action required

The current `config/settings.py` reads the environment variable `SECRET_KEY`; it does not read `DJANGO_SECRET_KEY`. It also loads `BASE_DIR/.env` and defaults to the weak value `change-me`. With `DEBUG=False`, startup is blocked until a real key is configured. Do not overwrite a currently configured key until the owner confirms it is safe to rotate.

In cPanel, open **Software → Application Manager**, find the existing Django/Passenger application, choose **Edit**, and under **Environment Variables** choose **Add Variable**. Set the variable name to `SECRET_KEY`, paste a newly generated Django key directly into the hosting form, click **Save**, then **Deploy**. Generate it inside the hosting terminal with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`; it is a random 50-character key. Never copy it to chat, GitHub, frontend files or logs. If Application Manager is unavailable, use the hosting provider's per-application environment-variable facility. The fallback `BASE_DIR/.env` file must be private, mode 0600, excluded from Git, and inaccessible from the public document root; restart Passenger after configuration.

SMTP is not required for this first delivery path: buyers receive their file and ticket replies inside the order portal. Do not enable an unreviewed email path to bypass the shared Communication Core. Marketing consent is not inferred from purchase.

## 3. Exact integration proposal — do only after approval

1. Back up the production URL/settings files and database. Preserve all unrelated changes.
2. Copy only reviewed `revenue_stream/` into the production source root. Exclude `__pycache__`, test outputs and any runtime database.
3. In the current `config/urls.py`, add exactly:
   `urlpatterns.append(path('costkit/', include('revenue_stream.urls')))`
4. Add `BASE_DIR / 'revenue_stream' / 'templates'` to the existing Django template `DIRS`. No replacement of installed apps, root URL routing or authentication.
5. Ensure `/costkit/` cannot be cached by the existing service worker: add `costkit` to its private/network-only route exclusion. Especially protect order, access, download and callback paths. All private responses already include `no-store` and `noindex`.
6. Link the sales page from Restaurant and Marketing; add the public URL to the sitemap only when live. Do not add checkout/private routes. Add owner panel `/costkit/owner/` to the existing owner dashboard.
7. Use existing HTTPS. Do not trust arbitrary forwarded-IP headers. Restrict database/artifact backup access. No public source ZIP.
8. Run regression tests, deploy the approved code with live checkout OFF, and check rendering/security headers in staging/private preview.
9. Test sandbox using a separate isolated harness and real provider-issued sandbox configuration. Never count sandbox events as revenue or write them to the production order DB.
10. After explicit approval, enable live checkout and perform one agreed real low-value purchase with the owner/customer; verify exact amount, callback replay, receipt, download and support. Any refund is a separate human bank/provider action, not an Agent withdrawal.

## 4. Recovery and operations

- Callback/recheck verifies amount from the immutable database row, not query parameters. Repeated verification does not duplicate revenue.
- `request_unknown` means the provider request outcome is uncertain. Do not automatically initiate another request. Reconcile using order ID, provider dashboard and audit evidence; confirm whether any payment occurred before creating a new order.
- Paid files are archived by SHA-256 under the private data directory; retain purchased versions across updates. Do not delete archives while customers retain delivery rights.
- Monitor disk space and backups, paid-with-zero-download cases, failed verifications, unaddressed tickets and refund requests daily. The UI does not pretend email alerts are configured.
- Weekly owner export/reconciliation: gross verified receipts, actual provider fees, taxes, refunds, operating costs. Only verified net distributable revenue can enter the existing 90/9/1 protected policy. This module does not allocate or transfer money.
- Rollback: set `ZM_COSTKIT_LIVE=0` to stop new checkout; retain callback, recheck, order access, download and support for existing buyers. Do not remove the whole module or order DB as a rollback.
- Recovery of a lost order password is manual and identity/evidence based; no unverified email reset. Do not send passwords through chat.
- Retention/deletion procedure requires approved legal/accounting retention periods and owner review; no automatic destruction is enabled.

## 5. Product and distribution boundary

This v1 is a domestic Iranian checkout with a bilingual downloadable product. It is not an international payment solution. Any future international provider needs verified country/entity eligibility, terms and lawful settlement; no bypass or borrowed account.
No customer messages, paid ads or third-party outreach were sent. Draft launch material is in `MARKETING.md`; obtain channel/audience approval before sending it.

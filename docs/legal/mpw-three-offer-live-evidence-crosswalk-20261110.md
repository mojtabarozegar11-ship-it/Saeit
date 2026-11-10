# MojPlayWin three commercial offers — live-versus-evidence crosswalk

**Date:** 2026-11-10. **Mode:** read-only evidence review; no checkout submission, blockchain payment, file download, live-host write or legal certification.

## 1. Current browser observation (public product details, not paid purchase)

| Native product ID | Observed public page | Displayed USD price | Buy link visible | Delivery proven by this observation? |
| --- | --- | --- | --- | --- |
| 72 | `https://mojplaywin.com/store/product/72/` | 7.50 | Yes, `/commerce/book/72/` | No |
| 225 | `https://mojplaywin.com/store/product/225/` | 4.00 | Yes, `/commerce/book/225/` | No |
| 879 | `https://mojplaywin.com/store/product/879/` | 6.80 | Yes, `/commerce/book/879/` | No |

All three pages described guest email, a TRX invoice and server-side payment confirmation. Those are **buyer-facing statements**, not independently verified end-to-end payment or exact private file delivery. No buy link was followed and no POST was submitted in this review.

The Atelier public detail page claimed a client-ready HTML/CSS/JS ZIP, **five original SVG illustrations**, a one-site/client usage license and exclusion of demo photographs. These claims do not establish who created the illustrations, whether embedded third-party assets can be resold, or whether the current paid ZIP matches the preview.

## 2. Existing first-party source evidence and limitations

| Evidence reference | What it actually supports | What it cannot establish |
| --- | --- | --- |
| `catalog/mojplaywin/atelier-interior-kit-v1.json` on main | Historical private ZIP name and SHA-256, original 11-member repack verification claims, `preview_only`, `checkout_enabled=false`, `paid_delivery_enabled=false`; records source provenance of a draft | Present-day production metadata, paid checkout safety, or intellectual-property title |
| `scripts/atelier_interior_register_native_draft_20261021.py` on main | Intended registration with `license_verified=false`, `quality_approved=false`, `factory_publication_permission=false`, `payment_live=false` | That these false flags still reside in today's live database, or that the proposed license is enforceable |
| `scripts/atelier_interior_release_probe_20261021.py` on main | Has non-mutating private candidate matching and ZIP-structure checks, for a specific historical hash | This cycle's actual cPanel contents; signature/asset provenance; signed author-to-seller license |
| `docs/marketing/atelier-interior-website-launch-checklist-20261024.md` on main | Historical marketing claim of five SVG images, demo-photo exclusion and one-site license | Original source proofs or a legal license grant from the owner of every asset |
| `.github/workflows/mpw-two-books-payment-depth-20261018.yml` on main | Historical reference digests for two PDFs and selected metadata consistency checks | Independent origin of chess diagrams, story illustrations or seller rights |
| `mpw_guest_trx_20261020/guest_product.py` on main | A guest-product code path checks boolean metadata `license_verified`, file presence and other release flags | Authenticity of the legal evidence behind those booleans; actual live deployment of this code |
| `command_center/mpw_two_books_panel.py` on main | Read-only dashboard differentiates metadata sale-ready flags and paid-order data | Actual blockchain settlement, rights clearance, and verified buyer file access |

**Confirmed discrepancy requiring reconciliation:** historical Atelier catalog declares preview/no checkout; on 2026-11-10 the public product page displays `$6.80` and an active-looking Buy link. It remains **unknown** whether the buy route currently enables invoice creation, whether the live database flags differ, or whether a valid private ZIP is delivered. Neither the old catalog nor the public button alone settles those questions.

## 3. Connected-drive discovery results

Read-only Google Drive and Dropbox filename/content searches were performed for exact private filenames and combinations of `chess`, `Taniya`, `atelier`, `MojPlayWin`, `copyright`, `license`, `rights`, and `original manuscript`.

- No *identifiable exact-match* original editable manuscript, Atelier source ZIP, signed rights assignment or product-specific third-party asset license was found in the accessible returned results.
- Some Google Drive results contained those keywords inside **other projects** (e.g. agricultural-economics release documents or research manuscripts). These are not evidence for the three MojPlayWin SKUs and were not promoted into the rights register.
- Search absence is not proof that a file does not exist in a restricted account, private cPanel directory, unindexed folder or off-platform archive.
- No account sharing, copy, move, download, deletion or access-permission changes were performed.

## 4. Reconciliation decisions and next non-mutating evidence requests

1. **SKU 72 — HOLD on independent rights claim:** obtain editable chess book, dated source history, diagram/illustration/cover licenses, authorship and seller authority; verify exact current paid PDF hash separately.
2. **SKU 225 — HOLD:** obtain original story manuscript and illustration source projects, source licenses and author-to-seller rights; verify exact current paid PDF hash separately.
3. **SKU 879 — HOLD / production conflict:** map the 11 historical ZIP members, especially all `assets/` and external dependencies, to their authors and rights; obtain authorized independent current cPanel product flags and hash. Reconcile paid storefront messaging with the historical no-sale catalog before any representation of full commercial readiness.
4. **All three:** distinguish copyright ownership, licenses for embedded materials, permission to distribute through MojPlayWin, technical delivery evidence and payment readiness. No single flag, digest, CI green status or public page implies all five.

## 5. Exact outcome

| Metric | Measured result |
| --- | --- |
| Public product pages observed | 3/3 |
| Existing source references mapped in this crosswalk | 7 |
| Exact product-related ownership/license packets independently authenticated | 0/3 |
| Paid invoice POSTs, on-chain transactions, or paid-file deliveries performed | 0 |
| Changes to live checkout, VPS, cPanel or customer records | 0 |

**Status:** investigative source crosswalk only. Remains **not legally cleared by this review**; this does not prove infringement. Keep PR in Draft, with no merge, deployment, email, financial commitment or live checkout mutation absent separate approval.

## 6. Cycle 43 — Sites-owned preview provenance, not commercial-stock provenance

The Sites owner account's metadata exposed the **actual preview project ID** `appgprj_6ad8bc1db4748191af8fb37df7c793aa`, slug `atelier-interior-kit-demo`, and the same URL that appears in the historical product catalog. As of 2026-11-10 the current Sites project **metadata title** is `PLT WorldForge — Project Decision Workspace`, even though its description still refers to a professional interior-design website kit. This is a **metadata identity discrepancy**, not proof of what the current browser actually renders.

The project has 14 saved versions. The oldest listed version has a 12-file Sites release archive, the latest has 29 files, and the latest source revision is `831f38b000d60e19c3306b3f85ac362bdc45017b`. Those archives and the historical **11-member private paid ZIP** are independently identified artifact families, with different SHA-256 digests. They have **not** been byte-comparison audited or proven equivalent.

The separate source-owned product template explicitly labels the Sites link a **related concept**, warns that WorldForge/planner tools and demo photographs are not sold, and refers to `/site-preview`. The Sites title drift confirms why the related concept must never be presented as the paid ZIP or as a copyright/redistribution-rights certificate.

New source evidence snapshot: `catalog/mojplaywin/atelier_demo_identity_snapshot_20261110.json`. A read-only, fail-closed validator and six offline contract tests detect claims that Sites metadata alone confirms copyright, exact paid ZIP equivalence or commercial rights. They cannot independently authenticate a third-party asset license.

**Source-only remediation in the Draft PR:** `core/templates/brands/mojplaywin/product.html` is now designed to withhold the guest checkout link unless the product is active, all relevant stock/licensing/publication flags are true and its rights review explicitly says `independently_cleared`. This is *conditional rendering*, not an independently verified live clearance process; the underlying evidence and live deployment still require separate review. Existing production was not changed.


## 7. Cycle 44 — confirmed CI, marketing claims correction, and limits of code visibility

**CI result for Cycle 43 head `41636f4d2e7f287d6bb8d4b605c3b9c316bfc544`:** all three GitHub workflows (`CI`, `Django CI`, `Factory Evidence Quality Policy Tests`) completed successfully. The PR remained Draft and unmerged at this observation. Green CI validates the checked source and tests, **not live rights or a completed payment/delivery**.

Additional connected Google Drive searches for `atelier`, `taniya` and `chess` returned only unrelated agricultural economics or gemology documents. Corresponding scoped Dropbox searches returned zero matches; exact SKU 72, 225 or 879 creation projects, authorship grants and redistribution licenses were **not identified** in accessible results. A search miss cannot prove nonexistence elsewhere. No file was shared, copied or deleted.

**Specific issue corrected in Draft source only:** the product 879 marketing text previously described five SVGs as `original` and one-site/client usage as an already-granted `license`, despite missing signed rights evidence. Those claims were softened to unverified historical catalog descriptions, a rights-pending warning was added for all three products, and source tests were updated. This reduces unsupported assertions; it does not establish new ownership, transfer IP, or change the live store.

The checked branch includes `mpw_guest_trx_20261020/guest_product.py`, which checks flags for the **two book SKUs**, but **the referenced `mpw_commerce/product_checkout_page.py`, `mpw_commerce/buyer_orders.py`, and `core/cryptopay_checkout.py` paths were not retrievable from that GitHub branch** (404 from the file API). This is a repository-source visibility gap, **not a claim that the live Django runtime lacks those modules**. A template-only CTA guard is insufficient to prove a direct checkout URL cannot create invoices. No checkout POST was attempted.

### General rights standard used for documentation, not an individual legal ruling

- WIPO explains that copyright protection ordinarily arises automatically and that licensing means authorization of uses within a defined scope: <https://www.wipo.int/en/web/copyright/faq-copyright>.
- WIPO identifies literary, artistic, photographic and software works among potentially protected categories, with originality relevant to protection: <https://www.wipo.int/en/web/copyright/protection>.
- The U.S. Copyright Office's permission guidance cautions that a composite work may incorporate separately owned content even if one person publishes the whole: <https://www.copyright.gov/circs/m10.pdf>. This is a useful evidence principle, **not a finding about governing law for MojPlayWin**.

### Release gate still open

Before removing the rights hold, obtain and examine, for each exact current sellable file: (1) current private-file hash and readable manifest, (2) dated editable creation history, (3) component-by-component authorship and third-party asset/license inventory, (4) the actual grant from author to the named selling entity and proposed buyer terms, (5) independent review of scope and authenticity, and (6) effective server-side direct-URL checkout and entitlement gates. The last item requires authorized read-only access to the deployed runtime/source, not merely CI or metadata booleans.

**Cycle 44 conclusions:** GitHub workflows 3/3 green for the prior head; accessible independent documentary rights packets 0/3; live host and transactions untouched; no email, ticket, fee, merge or deployment.


## 8. Cycles 45–46 — new-invoice gate without rewriting prior paid entitlements

**Cycle 45:** source-only template regression was repaired at commit `18a4a2311dc083e4bcbb7bb62090c4de5766a930`; the three PR-triggered workflows completed successfully for that commit. A read-only visit to `https://cpanel.zomorodmelal.ir/` reached a login form only. Authenticated live source, effective direct checkout URL, stock hash and account state were **not** inspected; this cannot be claimed as a production verification.

**Cycle 46 change, Draft branch only:**

- Added `mpw_guest_trx_20261020/guest_rights.py`: a fail-closed **new-order-only** predicate for books 72 and 225. It requires an active product, `rights_review_status == "independently_cleared"`, and every five named release flag to be exactly boolean `true`. SKU 879 is intentionally outside this historical two-book route.
- In `mpw_guest_trx_20261020/guest_checkout_view.py`, the `action == "start"` POST branch now checks the predicate *before* calling `issue()`; if the check fails, a user-facing hold notice explicitly says not to send funds.
- Existing `action == "verify"`, `guest_download.py`, `guest_product.py`, receipt records and private files were **not** changed by this gate. Not adding a new hold to those code paths is important for preserving prior purchaser entitlements, but does not prove every earlier paid order can be retrieved in production.
- Added eight offline regression methods in `tests/test_mpw_guest_rights_new_orders_20261110.py` covering affirmative and negative cases, strict boolean flags, invalid metadata, AST placement before `issue()`, separation from paid receipt/download and a pure helper.
- The last test-only update is `e2f1f14e4bfad35ce158e74de86d44787631e17a`. As of initial review, the Factory Evidence Quality workflow passed while the two broader CI workflows were still pending; their final outcome must be checked separately.

**Narrow applicability:** This change protects only the tracked *legacy* two-book guest-invoice start function if that function is actually deployed and invoked. It **does not demonstrate** that the live `/commerce/book/<id>/` route uses this handler, nor does it cover other order-creation APIs or the SKU 879 paid offer. A metadata status is a workflow switch, not independently authenticated rights documentation. No status was set to `independently_cleared` here.

**Unchanged measured evidence:** exact three-product independently verified legal packets **0/3**; live deployment/merge **0**; paid buyer-flow transactions initiated in this review **0**. Retain the legal hold pending independently documented file/source provenance, seller authority, third-party component rights and authenticated route-by-route production review. No outbound mail/ticket, host write, financial commitment or live order mutation.


## 9. Cycle 47 — effective TRX guest adapter boundary (source only)

The previous two-book `mpw_guest_trx_20261020/guest_checkout_view.py` is **not** the only apparent order-creation path. First-party source discovery identified the separate `services/mpw_trx_guest_commerce.py` adapter. It wraps `start_order` over the existing `_start_order` ledger handler and renders `/commerce/book/<id>/`-style product checkout via `patch_public`; another referenced path is `/commerce/trx-easy/start/<id>/`. The adapter imports the effective `rights_cleared_for_sale` routine from `services.mpw_trx_commercial_context`, whose cPanel code is managed by a reviewed historical rights patch script rather than present as a plain tracked module. **This is evidence of an intended effective source path, not independently authenticated deployment on the live host.**

**New Draft-only protections:**

1. `services/mpw_trx_new_sale_policy.py` defines a pure fail-closed review predicate for SKUs 72, 225 and 879, requiring exact boolean release flags and `rights_review_status == "independently_cleared"`. These metadata switches are **not evidence of copyright**, must not be enabled without verified source/grant documents and must not be treated as a signed rights finding.
2. `services/mpw_trx_guest_commerce.py` now checks the shared predicate, stock eligibility and the existing asset/document-hash-linked `rights_cleared_for_sale` routine before rendering the checkout page and before invoking the new-invoice `start_order` ledger handler. The start-order check occurs before guest-principal creation and before the invoice handler, so rights-held offers cannot create orphan guest identities through this route. Existing POST CSRF protection still precedes the wrapper, and eligible new customers retain the original guest identity rate limiter. Unapproved attempts are rejected by the host/policy preflight rather than reaching that identity limiter; production load/rate behavior still needs verification.
3. The existing `show_invoice`, `invoice_status`, `reconcile_invoice`, `download_paid`, receipt records, private stock files and prior buyer entitlements were not given this new-sale status test.
4. Twelve new offline regression methods in `tests/test_mpw_trx_new_sale_policy_20261110.py` inspect SKU/flag behavior and AST placement of the invoice guard. Two isolated execution tests additionally verify that a held new sale does not call guest identity or invoicing, while an existing invoice-access dispatch never invokes the new-sale gate. They create no real invoice, charge no funds and access no customer records.

**What remains unproven:** the effective deployed URL resolver and server versions, especially any unwrapped direct `_start_order`, alternative POST/API or direct `/commerce/book/<id>/` handler, must be compared through authorized authenticated read-only inspection before declaring every live invoice path protected. Historical workflows contain a reversible cPanel rights patch, but its presence in GitHub does not verify installation or current rights metadata. No change was made to the live host in Cycle 47.

**Status carried forward:** CI for the preceding Cycle-46 commit `32e931268474e73facb2b8f8c05476cac1343496` is **3/3 successful**. The current Cycle-47 code needs its own fresh run result; this historical green result is not transferred to a later commit. Legally authenticated exact-SKU rights packets remain **0/3**. Draft/no merge/no deployment/no payment/no email/no ticket.


## 10. Cycle 48 — URL table binding coverage, without deployment

**Prior head verification:** Commit `096bab9a97b1ca00fbb868f14f65db90c1976376` completed **3/3 successful** PR-triggered workflows (CI, Django CI and Factory Evidence Quality). This validates the preceding Draft source, not the live checkout.

**New source correction:** `services/mpw_trx_guest_commerce.patch_commercial` previously rebound registered `COMMERCIAL_URLPATTERNS` only when its type was `tuple`; an equally legitimate `list` container would have skipped the final URL callback rewrite while still marking the checkout adapter as installed. The Draft source now supports both `tuple` and `list` and preserves the original collection type. An explicitly supplied unsupported collection type fails rather than silently claiming installation. `None` remains allowed for legacy integrations that attach views later; this is still a live-route provenance limitation.

**Two targeted offline checks** were added to `tests/test_mpw_guest_telemetry_isolation_20261108.py`: one confirms a list-based table binds new-order, invoice and paid-download URLs to their respective wrapped functions; the other confirms an unsupported table does not set the installed flag. They do not create orders, send email or call the chain.

**Remaining release evidence:** authenticated actual deployed `COMMERCIAL_URLPATTERNS` type/callback identity and the effective `/commerce/trx-easy/start/<id>/` route must be captured read-only, with original paid download/recovery proven unaffected. Exact product rights packets independently authenticated: **0/3**. All current Cycle-48 changes remain GitHub Draft only, without merge, cPanel/VPS write, payment, ticket or email.


## 11. Cycle 48 — fresh public buyer-form observation, GET only

A read-only cloud-browser visit on **2026-11-10** to three public checkout pages returned populated page titles and visibly rendered buyer forms, with these exact DOM facts:

| Public GET page | Observed form action | Method | Required HTML email input | Visible price |
| --- | --- | --- | --- | --- |
| `/commerce/book/72/` | `/commerce/trx-easy/start/72/` | POST | `type=email`, `required=true`, `name=email` | USD 7.50 |
| `/commerce/book/225/` | `/commerce/trx-easy/start/225/` | POST | `type=email`, `required=true` | USD 4.00 historically; price not reread in this browser step |
| `/commerce/book/879/` | `/commerce/trx-easy/start/879/` | POST | `type=email`, `required=true` | USD 6.80 |

The product 72 form also contained a CSRF hidden input, visible invoice-creation button and text warning that cross-device email recovery remains unavailable. The SKU 879 public checkout **currently presents an invoice-creation form despite the historical preview-only catalog and absent independent rights packet**. This is a buyer-facing configuration discrepancy, not proof that the POST succeeds or that rights are infringed.

**Not performed:** no input was filled, no POST or invoice creation attempted, no chain transaction, customer session mutation, email, ticket or deployment. Required HTML email attributes are **client-side affordances**, not independent proof of server-side email validation. The Draft-only rights guard would need a separately approved deployment and authenticated production-source comparison to affect this live form.


## 12. Cycle 49 — fail-closed start URL binding and single-email preflight

Source-only additions to `services/mpw_trx_guest_commerce.py`:

- A supplied tuple/list `COMMERCIAL_URLPATTERNS` must contain a recognized `/start/` entry. An empty list or invoice-only table raises rather than asserting `_mpw_guest_checkout_installed=True` while the purchase entrypoint remains unpatched. Cycle 50 strengthens this: absent, malformed, or duplicated start routes now also fail **before any public callback is modified**; all five original handlers must be callable.
- Every new `start_order` call runs the existing SKU/rights guard, then checks that **exactly one** submitted `email` value is present, unpadded, at most 254 characters and accepted by Django's `validate_email`, **before** creating a guest identity or calling the invoice handler.
- Invalid new-sale email input is denied without creating a guest principal or invoice in isolated tests. Existing invoice lookup, payment reconciliation and paid download do not demand a second email or new rights authorization.
- `tests/test_mpw_trx_email_gate_20261110.py` and an additional route-table regression in `tests/test_mpw_guest_telemetry_isolation_20261108.py` cover normal, missing, duplicate, malformed and whitespace emails, denial before mutation, and continuity of paid-invoice access.

**Limits:** This source patch is not deployed. It proves neither how `services.mpw_trx_commercial_web._start_order` stores the submitted email nor whether the production system sends a receipt or supports cross-browser recovery. The referenced underlying runtime module is not available at this GitHub path, so email-to-order persistence still requires an authorized cPanel/server read-only inspection. A green CI run is not a rights packet or a successful real checkout. Do not issue invoices or send payments during rights HOLD.

## 13. Cycle 50 — verify deployment-hook shape before route mutation

The historical `scripts/mpw_guest_checkout_live_release.py` adds `patch_commercial(globals())` after `COMMERCIAL_URLPATTERNS` is defined, so an absent table is not a valid expected production integration. Preflight now checks the entire route table and all five underlying handlers before replacing any `start_order`, invoice, reconciliation or download callback. Isolated regressions cover absent, duplicated, malformed and missing-handler cases. A successfully installed marker can no longer arise from these invalid shapes in this adapter.

The live release script also demands an exact historical guest module SHA-256 before an upgrade. Therefore the new source is **not automatically deployable** by that script; any eventual release needs separately authorized, reviewed preflight and compatibility work, not an override or weakened digest check.

The underlying cPanel module `services/mpw_trx_commercial_web.py` is referenced in source and historical runtime scripts but not present as a GitHub-tracked file at the referenced path. The adapter validates email formatting; **email persistence to a paid invoice and cross-browser recovery remain UNKNOWN** without read-only runtime inspection. No live order or invoice was created, and no release, mail or payment action was taken.


## 14. Cycle 51 — cPanel read-only source bridge and live recovery disclosure (2026-11-10)

### Read-only evidence and exact limits

- The authenticated cPanel File Manager showed `/home/zomorod2/Saeit-staging/services/mpw_trx_commercial_web.py` (listed as modified 2026-11-06). Its `_start_order` calls `_select_order`, then `services.mpw_trx_guest_delivery.record_invoice(invoice_id, request.user)`, before returning the invoice redirect. The file defines the five standard `COMMERCIAL_URLPATTERNS` and invokes `patch_commercial(globals())`.
- `/home/zomorod2/mojplaywin.com/passenger_wsgi.py` explicitly sets `APP='/home/zomorod2/Saeit-staging'`, inserts that app path into `sys.path`, changes working directory to the same path and sets `SAEIT_ENV='production'` before loading `config.wsgi.application`. This establishes the **configured public application source path**. It is not direct proof of the exact modules currently cached by an already-running Passenger worker.
- The cPanel guest adapter `services/mpw_trx_guest_commerce.py` (listed as modified 2026-11-07) persists a submitted guest email to `user.email` when that field exists, rejects a different email on a reused guest principal, and wraps the five commerce handlers. Its **deployed-file listing and viewed source lack the new Cycle-49 single-`email` / Django-validator preflight and Cycle-50 all-handler/route-table preflight now on the Draft GitHub branch**. The public app is therefore not proven to have these latest Draft-only protections.
- `services/mpw_trx_guest_delivery.py` uses `GuestTrxDelivery.objects.get_or_create(order=pi.order, defaults={'email': email})` to bind the guest email to the order's existing payment intent. The invoice/receipt outbox sender checks `MPW_GUEST_EMAIL_SEND_APPROVED`. Code presence proves an intended persistence pathway, **not** database migration completion, outbox success, actual email transmission, or independent recovery from another device.
- `services/mpw_trx_email_recovery.py` defines `GuestOrderEmail` claims, recovery tokens, and guarded recovery routes. Its request endpoint requires `MPW_GUEST_RECOVERY_EMAIL_APPROVED=True` to issue recovery mail. Actual runtime flags and migration `0040` were **not inspected**; no outbound mail was sent.
- The publicly visible checkout `https://mojplaywin.com/commerce/book/879/` shows an email-entry field and a TRX invoice button. It expressly discloses **'Email recovery on another device is not yet available.'** No submit was made, and no order or invoice was created.

### Revised evidence classification

| Question | Cycle-51 evidence classification |
|---|---|
| Is cPanel direct File Manager access working? | PROVEN — authenticated and used read-only |
| Does the public Passenger bootstrap point to `Saeit-staging`? | PROVEN — bootstrap source |
| Is there source code for guest-email persistence and order-email binding? | PROVEN — inspected commerce, guest and delivery modules |
| Is the new strict Cycle-49/50 Draft guard present in the examined cPanel adapter? | NO — older adapter present; Draft improvements not deployed |
| Is email recovery available across devices to public customers? | NOT RELEASED according to public checkout disclosure; backend operational state still requires checking |
| Were schema migrations, merchant wallet activation, actual sales or outbound delivery verified? | UNKNOWN — no DB/customer records, credentials, payment or email actions |
| Are the three offer-rights packets independently cleared? | 0/3 independently cleared in the current rights register; do not infer rights from checkout visibility |

### Release boundary and CI

For commit `74f3d08a9f2f4b807a3de0d1e3c94d77a2e4270a`, GitHub reports Django CI, CI, and Factory Evidence Quality Policy Tests all **completed / success (3/3)**. These are source-workflow results, not proof of an approved deployment or commercial readiness.

**No merge, deploy, file mutation on cPanel, deletion, order, settlement, email or support ticket occurred.** The immediate next safe checks are a read-only comparison of live adapter digests, recovery schema/migration existence and non-sensitive runtime feature readiness. Do not bypass the historical release SHA gate or expose secrets/customer data.

## 15. Cycle 52 — authenticated host migration and active URL-order evidence (2026-11-10)

### Read-only evidence gathered on the configured cPanel application path

1. The actual file `/home/zomorod2/Saeit-staging/core/migrations/0049_mpw_guest_email_recovery.py` exists and is readable in File Manager (listing timestamp 2026-11-07 10:08 a.m.). It depends on `core.0048_business_market_architecture` and defines **three** models: `GuestOrderEmail` (unique protected order relation and email digest), `GuestRecoveryToken` (unique token digest, expiry and consumption) and `GuestRecoveryRate` (rate-limit bucket). This proves a **migration file is present**, NOT that the migration ran in the live database.
2. `/home/zomorod2/Saeit-staging/mpw_commerce/migrations/0004_guesttrxdelivery.py` exists and is readable (listing timestamp 2026-11-02 4:55 p.m.). It creates `GuestTrxDelivery`, a protected one-to-one order link containing guest email, separate invoice/receipt states and attempt counters, plus an email index. Database rows, delivery jobs, mail permissions and actual receipt sending were not read.
3. **Correction to Cycle 51 wording:** `core.0040_agenttask_bridge_idempotency.py` is a *different* migration; the observed guest-email recovery file is `core.0049_mpw_guest_email_recovery.py`. The `services/mpw_trx_email_recovery.py` source comment referring to migration “0040” is stale or incorrect. Do not instruct an operator to mark migration 0040 as the recovery schema. Before any future release, verify applied migrations by exact `app_label + name` on the *correct live database* using a separately reviewed read-only command, and reconcile the source comment; never fake or force migration state.
4. The configured host `config/urls.py` explicitly **appends** `include("mpw_commerce.urls")` but later **prepends** `path("commerce/book/<int:product_id>/", _trx_product)` from `services.mpw_trx_public_pages`. Therefore the *first-match route declaration in this inspected file* for `/commerce/book/<id>/` is the public TRX page, **not** `mpw_commerce.product_checkout_page` despite that same route existing in the latter app's `urls.py`. This is a file-level Django URL precedence finding; worker reload state remains unproven.
5. The `mpw_commerce.product_checkout_page` source requires an authenticated buyer, eight `MPW_COMMERCE_*` settings, released product metadata and a private file and wallet proofs. Its own docstring states QA-only integration. Those conditions **must not be cited as proof that the public guest route has the same gate**.
6. The `services/mpw_trx_commercial_web.py` **actual separate** `/commerce/trx-easy/start/<id>/` handler invokes the locked order selection with `_eligible(product)`, `rights_cleared_for_sale(product)`, private-file checks and merchant-wallet activation prior to issuing a payable intent. Its guest adapter is installed at module source level. Runtime flags, invoice issuance ability and any preexisting paid entitlement remain UNKNOWN until server-side verification; no POST was made.
7. The connected Draft branch `config/urls.py` has a different, shorter configuration than the host source and does not contain the observed live TRX route additions. The missing GitHub `services/mpw_trx_email_recovery.py`, `core/migrations/0049_mpw_guest_email_recovery.py` and other host-only files must be treated as **source-divergence evidence**, not a license to overwrite a production configuration with the GitHub branch. No merge/deploy is authorized or completed.

### New verified result and release prerequisites

- Prior Draft commit `d39a10f36ce8979263f42cd0d073cbd4c3a09e6c`: GitHub **CI, Django CI and Factory Evidence Quality Policy Tests all completed successfully (3/3)**. This is a source-test fact, not a deployed-workflow certification.
- Read-only host migration files directly viewed: **2/2** targeted files, with **0/2 confirmed applied** because no live migration-table check was performed.
- Exact independent rights dossiers for public SKUs 72, 225 and 879: **0/3** in the existing rights register. No claim of infringement is made.
- Invoice POST, on-chain payment, customer data read, new email, ticket, host edit, merge and deployment performed in this cycle: **0**.

**Fail-closed next gate:** confirm the effective running URL resolution and schema migration state without changing customer data, review the host-vs-repository source divergence and exact paid artifact rights, and only then propose a narrowly reviewed integration plan. The live email-recovery message remains “not yet available” and must not be contradicted by marketing. Preserve existing paid customers while withholding unverified new sales.

## 16. Cycle 54 — strengthen cPanel read-only probe root provenance (2026-11-10)

The Cycle-53 branch introduced `scripts/mpw_guest_runtime_readonly_readiness.py` and
`tests/test_mpw_guest_runtime_readonly_readiness_20261110.py`. The script is
**not a production release tool**. It limits database access to schema metadata
(`django_migrations` and table introspection) and does not read customer/order
rows, create invoices, send email, deploy, or migrate.

**New, actionable correction in Cycle 54:** before importing Django or making
the schema/route inspection, the probe now verifies the cPanel public
`.htaccess` explicitly declares **exactly one** `PassengerAppRoot` pointing
to the known `mojplaywin.com` public root. A missing, symlinked or oversized
file (>100000 bytes), no directive, duplicate directive, malformed quotes or
root of another site yields a generic blocked reason and aborts. This closes
a possible false positive where an otherwise correct `passenger_wsgi.py`
file belongs to an unregistered or differently registered website. It is
a **configuration-file validation**, not a claim to have inspected the
effective running Passenger worker or its cached code.

**Evidence checks:**
- Prior Cycle-53 commit `94a47375cdcce649b7e78fa5926c8536c105351d`:
  all three PR workflows (CI, Django CI and Factory Evidence Quality Policy
  Tests) were verified **completed/success (3/3)**.
- Current Cycle-54 probe and contract-test source files compile successfully
  offline. The 13 contract-test methods were executed against the exact
  branch contents in a no-filesystem-write, in-memory harness; **13/13 passed**.
  Seven additional parser fixtures were checked separately and **7/7 passed**.
  These results are checks of a read-only diagnostic and do not establish
  release readiness or live runtime state.
- At the first check for Cycle-54 head
  `7fd9693b35a39b849fdb90de89ea481d12e51c08`, Factory Evidence
  Quality was successful, while CI and Django CI were pending. Do not
  count these pending runs as successes without a new check.
- The production cPanel diagnostic itself was **not run** in this cycle:
  the previous authenticated browser session had expired. Therefore actual
  applied migration state, live flags, process-level URL resolution and
  operational cross-browser recovery remain **UNKNOWN**.

**Unchanged release hold:** independent SKU 72/225/879 rights packets
authenticated here **0/3**; no live invoice/payment/delivery validation
and no permission to merge or deploy. No payment, email, support ticket,
server write, order creation, or deletion occurred.

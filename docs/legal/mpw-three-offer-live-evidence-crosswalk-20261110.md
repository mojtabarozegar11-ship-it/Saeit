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
4. Ten new offline regression methods in `tests/test_mpw_trx_new_sale_policy_20261110.py` inspect SKU/flag behavior and AST placement of the invoice guard, without creating an invoice, charging funds or accessing customer records.

**What remains unproven:** the effective deployed URL resolver and server versions, especially any unwrapped direct `_start_order`, alternative POST/API or direct `/commerce/book/<id>/` handler, must be compared through authorized authenticated read-only inspection before declaring every live invoice path protected. Historical workflows contain a reversible cPanel rights patch, but its presence in GitHub does not verify installation or current rights metadata. No change was made to the live host in Cycle 47.

**Status carried forward:** CI for the preceding Cycle-46 commit `32e931268474e73facb2b8f8c05476cac1343496` is **3/3 successful**. The current Cycle-47 code needs its own fresh run result; this historical green result is not transferred to a later commit. Legally authenticated exact-SKU rights packets remain **0/3**. Draft/no merge/no deployment/no payment/no email/no ticket.

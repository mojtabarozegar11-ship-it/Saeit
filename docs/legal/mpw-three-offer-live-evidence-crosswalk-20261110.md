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

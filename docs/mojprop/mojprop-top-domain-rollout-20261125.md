# mojprop.top commercial rollout — 25 November 2026

**Decision recorded:** use `mojprop.top` as the international commercial front door for MOJ PROP (simulated challenge) and MOJ SIGNAL (research/signal subscriptions). No unrelated store or game products belong on this domain.

**Implementation status: plan committed to a review branch; no DNS, hosting, code-runtime, checkout or customer-data change has been made.** This is necessary because the current source explicitly marks the 30 TRX SKU as source-only/no-payment, the signal products as inquiry-only, and the existing merchant binding as `mojplaywin.com`. No production transaction or customer revenue is evidenced by this plan.

## Architecture decision

Bind `mojprop.top` to the **existing MojPlayWin Passenger/Django application and MariaDB**, after the cPanel provider confirms the effective virtual host and capacity. Keep the existing database, merchant records, customer orders, IDs, logs and recovery paths. Do not clone the application/database, run migrations, or move old orders. Preserve existing `mojplaywin.com` routes as working aliases until redirect, cookies, CSRF, receipt/download, recovery, and merchant-domain behavior are separately confirmed.

The new host needs an explicit tenant/merchant mapping in application configuration and a reviewed payment adapter. The current checkout is bound to `mojplaywin.com`; a new host must not pretend to be supported by changing browser input or weakening that binding. Use one central operator identity, `mojtaba.bot.ai`; no second bot or unsupervised trade executor is implied.

## Target route map

| mojprop.top route | Purpose | Existing source/route to reuse | State |
| --- | --- | --- | --- |
| `/` | International home; links only to Prop and Signals | New composition | Not built |
| `/prop/` | Simulated challenge terms and product | `/moj-prop/`, Starter30 page | Existing source; host mapping pending |
| `/signals/` | Free research sample, archive and risk disclosures | `/moj-prop/signals/` | Existing inquiry funnel; paid feed inactive |
| `/subscriptions/` | Daily/weekly/monthly/quarterly/yearly plans | Signal plan source and inquiry flow | Recurring delivery/entitlements not implemented |
| `/payment/` | Order-specific TRON invoice/status and policies | Existing MojPlayWin checkout components | New-domain merchant binding and sale release unproven |
| `/dashboard/` | Customer orders, access and subscription state | Existing order/recovery records if compatible | No new dashboard assumed |
| `/support/` | Support and complaints | Existing Moj Prop contact/intake | Map after seller/contact policy confirmed |

Only actual active plans may have a “buy” action. Until recurring delivery and cancellation/refund rules exist, plan cards must say “not available” or accept a clearly labeled request for terms; they must not create an invoice or imply an active subscription. A dashboard must authenticate the existing customer/order rather than expose records by guessable IDs.

## Twenty rollout actions and evidence

Status labels: **DONE** = completed in this source review; **OPEN** = requires implementation/evidence before that release stage. No action below claims a production sale.

1. **DONE** — Record the user's domain-purpose and two-product decision in this release plan.
2. **DONE** — Identify the effective code repository (`Saeit`) and private gateway snapshot; do not create a parallel storefront.
3. **DONE** — Read the authoritative Starter30 release contract and native-TRX settlement contract.
4. **DONE** — Read the current Signal Desk release gates and existing plans.
5. **DONE** — Confirm current Starter30 state is source-only/no-payment and that the 30 TRX value is native TRX, not USDT.
6. **DONE** — Confirm signal plan identifiers exist only as educational weekly/monthly/quarterly requests; active recurring fulfilment is not evidenced.
7. **DONE** — Record existing merchant-domain binding to `mojplaywin.com`; do not bypass it.
8. **DONE** — Record the no-duplicate-database decision to preserve orders and customers.
9. **DONE** — Add the requested clean route map without adding unrelated products.
10. **DONE** — Separate the free/historical research sample from a live, paid signal claim.
11. **OPEN** — Confirm domain registrar account, authoritative nameservers, DNS records and control of the zone.
12. **OPEN** — Confirm the host's effective cPanel virtual-host/document-root mapping, available disk quota and whether an additional alias domain is included at no added cost.
13. **OPEN** — Add the domain to the existing host only after confirming it will route to the same intended Django/Passenger application; no second host purchase is assumed.
14. **OPEN** — Configure Django allowed hosts, trusted origins, HTTPS, CSRF, session-cookie and canonical-host behavior for both domains; retain old-host compatibility.
15. **OPEN** — Update merchant configuration and invoice contract so new invoices identify the correct domain and seller while keeping the owner-controlled TRON receiver fixed server-side.
16. **OPEN** — Reconcile the production database/schema mismatch tracked as Saeit issue #2392 before any backend migration or new payment/order model.
17. **OPEN** — Complete seller identity, supported-jurisdiction, service, privacy, complaints, cancellation/refund and delivery terms for both products.
18. **OPEN** — Implement server-issued, immutable order/invoice binding for the new domain and solidified TRON reconciliation; prevent duplicate txids and customer/order misassignment.
19. **OPEN** — Implement paid signal subscription entitlements, actual dated content pipeline, renewal/expiry/cancellation, delivery receipts and customer self-service before marketing recurring plans as purchasable.
20. **OPEN** — Back up and independently restore the existing app/database, publish from a reviewed release, verify all seven routes and all locale SEO signals, then complete one consented real buyer-to-settled-payment-to-delivery receipt before recording revenue.

## International SEO and customer experience

Keep the existing 20-language content work as the translation source, but publish unique, reviewed pages for each language and for each commercial intent. Add language switchers, reciprocal valid `hreflang` links, self-canonicals, a domain-specific sitemap, and internal links among the new domain's Prop, Signals, subscriptions, payment and support pages. Remove stale `mojplaywin.com` canonical/hreflang URLs from the new-domain copies only after both hosts and redirects are verified. Do not canonicalize every language to English.

For each language, research its actual commercial vocabulary (including regional terms for prop firm, simulated challenge and trading signals), write localized titles/descriptions and useful page copy, and measure Search Console impressions/clicks by query and country. “Page one” is a target, not a result that code can guarantee. Do not publish fabricated signal performance, trade histories, customer counts, payouts or testimonial claims. Distinguish simulated results from verified real-money execution.

## Current blockers and stop conditions

- `mojprop.top` did not resolve from the available execution environment during this review; this is not authoritative DNS evidence. Registrar nameserver/zone and host A/AAAA/CNAME targets are not available here.
- No authenticated registrar or cPanel zone-edit capability was available in this session. DNS and virtual-host changes remain unperformed.
- Existing code explicitly blocks Starter30 payment until release evidence is satisfied; existing signal pages provide educational material and requests, not paid recurring access.
- The current merchant mapping is for `mojplaywin.com`. Do not issue invoices for `mojprop.top` until the seller/merchant mapping, accepted terms and end-to-end settlement are reviewed.
- Existing source notes Saeit issue #2392 as a database migration/restoration blocker. Avoid production migrations or tenant changes before it is resolved.
- No additional hosting purchase is part of this design. Capacity and alias-domain entitlement must be confirmed with the current host before cutover.

## Progress snapshot

| Workstream | Complete | Remaining | Progress |
| --- | ---: | ---: | ---: |
| Source review and architecture | 10/10 | 0 | 100% |
| DNS and host binding (actions 11–13) | 0/3 | 3 | 0% |
| Application and database integration (actions 14–16) | 0/3 | 3 | 0% |
| Seller, payment and fulfilment (actions 17–19) | 0/3 | 3 | 0% |
| Backup, multilingual SEO and production acceptance (action 20) | 0/1 | 1 | 0% |
| **Production launch** | **0/20** | **20** | **0%** |

The completed items above are source review and architecture decisions, not deployment. Production launch remains at 0% until the OPEN evidence is obtained and an actual buyer is served.

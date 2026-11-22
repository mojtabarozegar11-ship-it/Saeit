# P0 — two sites, one bot: revenue conversion operating protocol
**Canonical executor:** `mojtaba.bot.ai` only. This repository provides source and deterministic local checks; it does **not** launch a new bot, scheduler, payment gateway or deployed service.

## Funnel with unambiguous denominators
- `views`: verified page views from authorized analytics (currently UNKNOWN).
- `inquiries`: unique opted-in, legitimate non-duplicate inbound service requests (currently UNKNOWN).
- `qualified`: human-accepted bounded scope with minimum evidence and consent (currently UNKNOWN).
- `approved_quotes`: explicitly authorized individual written scope/price (currently UNKNOWN).
- `paid_orders`: unique orders matched to **settled** valid payment receipts (currently UNKNOWN).
- `delivered_orders`: paid orders with owner-QC and customer-access confirmation (currently UNKNOWN).
- `collected_net_revenue`: settled received money less verified refunds/fees (currently UNKNOWN).

Never replace UNKNOWN with zero. Report ratios only when the denominator is independently measured and greater than zero. `conversion=inquiries/views`; `qualified_rate=qualified/inquiries`; `close_rate=paid_orders/approved_quotes`; `fulfillment_rate=delivered_orders/paid_orders`. A 200 response or a passing source test is not evidence of revenue.

## Lifecycle (no automated financial actions)
INQUIRY → MANUAL QUALIFICATION → OWNER APPROVES SCOPE/TERMS/PRICE/LAWFUL ROUTE → APPROVED INVOICE → SETTLED RECEIPT → QC-APPROVED DELIVERY → CUSTOMER CONFIRMATION → REDACTED LEDGER.

In the draft CLI, `payment_state` is always `not_requested` and `delivery_state` is always `not_delivered`. Only separate trustworthy settlement/delivery evidence may change those operational states.

## First demand experiments (no unsolicited bulk messaging)
- EN: one concrete checkout/sales issue, limited audit or bounded fix; approved public example only; no access secrets.
- FA: one crop/enterprise and one consistent accounting period; yield/revenue/cost assumptions documented.
- Public CTAs accept **inquiry only**. The owner must authorize each quote, communication, contract, financial transaction and production change.
- Human owner QC must reject unsupported causal claims, invented input values, and missing confidentiality controls.

## Required evidence before marking a milestone
- SOURCE: commit SHA, branch, path, source checks; independent CI status stated separately.
- LIVE: real route and domain identity, render, accessibility, link, inquiry test; currently **not independently verified**.
- COMMERCE: lawful collection, settled receipt ID redacted, entitlement/license status; currently **not verified**.
- DELIVERY: report checksum, private access route, client acceptance redacted; currently **not verified**.

## Progress reporting
Use separate source/readiness and commercial gates. For this cycle, 10 work-item completions out of 10 may show **100% of planned source tasks**, but never 100% revenue-readiness. Technical pass counts are not a substitute for collected sales.

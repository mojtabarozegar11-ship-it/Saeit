# C21 — Cross-brand replay is NOT proof of independent signal performance

Source-only security fix for the owner's second priority: selling market signals across owned websites and associated brand paths. The existing v1 `core.signal_history_evidence` adapter signed `source_id + event fields` but not `brand`. When multiple brands reused a provider source and key, the same v1 signed history could be presented as provenance for another brand. This could contaminate commercial subscription audits even if the independent trading-performance evidence gate still remained locked.

## Resolved in this branch
- Cryptographic envelope `mojtaba.signal.attested_source.v2` includes the **exact canonical 17-brand identity**.
- Both signing and audit require an explicit trusted brand; malformed/missing/unknown brands fail before accepting signed records.
- History commitment includes brand and cannot be silently reattributed; the audit result carries immutable brand/version metadata.
- Subscription-preflight only qualifies a v2 signed audit when its brand **exactly matches** the trusted merchant brand supplied by the internal adapter. Cross-brand and old-v1 audits fail closed.
- Legacy v1 signatures cannot be upgraded by changing a string; an authorized internal market adapter must explicitly re-sign the original source data for the right brand and preserve source/rights provenance.
- Existing market source audit `core.signal_source_evidence` from PR #2315 signs brand independently. These adapters should ultimately be reconciled to **one canonical signature version and one replay ledger**; they are currently two source APIs, not proof of two live systems.
- 17 source brands do NOT equal 17 owned public hostnames or 17 approved merchants. A signal is not sellable without legal authority, independently verified real history including losers/fees/slippage, customer delivery, refund terms and payment finality.

## Non-events
No broker order, advice, signal publication, paid alert, customer email, social media post, external server deployment, on-chain settlement, file entitlement or checkout was performed. No new bot, cron or scheduler is created; solely `mojtaba.bot.ai` remains the operational identity.

**Absolute prohibited target**: `Dr.mojtaba.rozegar`, its related Facebook Page ID `102203064721826` and Metricool brand `7317306`. No publishing or scheduling for this personal account.

**Release**: Draft only, based on exact parent PR #2310 head `d480bf29d2843cb89b7874e04e07787d48b3a015`. Parent advancement and PR #2315/#2316 changes must be reconciled before any merge. No hidden compatibility fallback to unsigned v1 events.

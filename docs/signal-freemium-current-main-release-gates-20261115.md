# Freemium educational signal funnel — current-main integration

**Source-only integration** of verified work from PR #2401, rebuilt on current main after paid-plan inquiry PR #2391 was independently merged. It does **not** activate real market signals, subscriptions, payments, trading, customer messages, or hosting publication.

## Exact implementation
- Public historical/hypothetical market-methodology sample at `/moj-prop/signals/#free-preview`; visible without entering contact information.
- 17 financial brand routes and 17 Arabic variants link to the one canonical free sample, alongside the existing manual educational research inquiry. Store/game links remain untouched.
- `?service=signals&tier=free` on both legacy and V4 forms records a **one-off free research request**, not ongoing marketing consent or a promise of a delivered signal.
- Paid plan selectors preserve the authoritative IDs `education-weekly`, `education-monthly`, `education-quarterly`. V4 preserves the existing main's exact SKU + indicative price notes-prefix and private receipt logic; no older V4 file replaces the current one.
- Switching to a non-signal service removes only unchanged system-authored notes. V4 free priority ignores even a concurrently supplied paid plan ID.
- Existing `/moj-prop-intake/` is CSRF-protected with validated consent, rate limit, durable `MojPropRequest`, backend allocated ID and signed receipt. No new customer identity, marketing subscription or payment backend was invented.
- Extra browser-run Node VM and Django integration tests validate paid/free routing, 34 brand paths, storage, and consent.

## Revenue release gates
1. Exactly latest-head green CI + Django CI + policy + source security and manual-release audit; verify PR mergeability and no main drift.
2. No automatic SSH deployment on merge. Hosted static Moj Prop page publication and Django API routing must be independently verified after authorized backup, restore and rollback.
3. No live financial trading signals until independently verifiable data-source adapter, accountable editor, dated content, jurisdictional legal clearance and explicit risk disclosures exist. A disclaimer alone does not remove legal requirements.
4. No TRON payment or paid access until seller, wallet, lawful accepting entity, invoice identity, independent settlement verifier, refund/revocation and valid merchant ledger are confirmed.
5. No recurring email update list without separate opt-in, verifiable subscription confirmation and unsubscribe; the current intake's consent is **only** consent to a manual one-off inquiry.
6. Sales revenue proven only by settled payment plus delivered customer entitlement; publication of a page/PR is not income.

**Next commercial milestone:** one historical free publication verified live; one lawful paid manually quoted research report with actual customer receipt and delivery evidence, if and only if all conditions pass.

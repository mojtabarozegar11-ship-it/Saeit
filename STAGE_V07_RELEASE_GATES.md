# MOJ Commerce v0.7 — two independent finalized TRON read sources

**DRAFT — code/testing only. No RPC credentials, no live second provider,
no production routing, no paid checkout and no VPS deployment.**

## New capability

`moj_commerce.quorum_verifier.verify_two_source_finalized_trx` is a
drop-in callable for the existing `MOJ_COMMERCE_FINALIZED_TRON_CHECKER` interface.
It requires exactly two operator-configured `TrustedSoliditySource` objects
with distinct operator IDs, distinct fetch callback objects and each its
own source-scoped API credential. Each independently fetches a solidified
TRX transaction **body AND execution receipt** from a trusted backend and
verifies tx ID, merchant-controlled destination, exact Sun amount, time,
solidified block number and timestamp against the server order and signed
event. Both independently validated normalized proofs must agree exactly.

Configuration absent / one provider down / same callback or operator /
invalid receipt / mismatched fields => `CommerceUnavailable`: **NO entitlement**.
No automatic fallback to one reader, no arbitrary browser-supplied RPC URL,
no private wallet key, no signing or broadcasting.

This module is NOT wired in production settings. The old one-provider function
remains for synthetic compatibility tests and existing source-only code, but
it does not meet this release's independence gate.

## Remaining operational proof

A different operator ID or Python callback does NOT prove two independent
real-world RPC operators. Before money, an owner-approved staging evaluation
must pin approved independent providers and their transport configuration,
prove separate node/vendor ownership, failover behavior and synchronized
SolidityNode finality, block receipt integrity, real latest solidified heights,
per-provider timeouts and rate limits, SSL trust, backup provider outage paths,
allowlisted network egress, secrets isolation and audited billing. Only then
bind `MOJ_COMMERCE_FINALIZED_TRON_CHECKER` to this new quorum callable.

TRON official docs explain that solidified data should use
`/walletsolidity/gettransactionbyid` and
`/walletsolidity/gettransactioninfobyid`; FullNode broadcast/inclusion is
not the same as a finalized successful payment:
https://developers.tron.network/docs/confirmation-semantics

## Acceptance

- Real Django test suite and PostgreSQL concurrency suite stay green.
- v0.7 synthetic tests cover separate per-provider API credential routing,
  unavailable provider, duplicate operator, shared fetch callback,
  bad receipt, wrong block time or amount, wrong network and bad config.
- Explicit provider configuration and production-verification tests are still
  separate blockers. No claimed 100/100 score or commercial readiness.
- All PRs remain draft. No main merge or production deployment by this change.

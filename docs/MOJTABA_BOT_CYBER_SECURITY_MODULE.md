# Mojtaba.bot.ai — Cyber Security and Origin Defense capability (internal only)

## One bot rule
**Canonical bot:** `mojtaba.bot.ai`. **Single capability:** `cyber_security`.
**Nested security function:** `origin_defense` (not an independent bot or agent).

Files:

```text
core/mojtaba_modules/
  __init__.py           # one-bot capability catalogue
  cyber_security.py     # signed scope gate + offline security findings
  origin_defense.py     # source-side / upstream mitigation review
tests/
  test_mojtaba_cyber_security.py
  test_mojtaba_origin_defense.py
```

No new Agent model row, independent worker, scheduler, daemon, website, login, account, trading entity or payment gateway is allowed. All work must be dispatched by the existing **verified** canonical bot runtime. This repository change alone does not prove that runtime exists or that it is already wired to these functions.

## What "defense at source" means

1. Protect the actual **origin server**: evaluate whether direct-origin connections bypass the site's CDN/WAF, restrict origin ingress to trusted proxy networks, consider authenticated origin pulls / mutual TLS or outbound-only tunnel, and validate expected Host/SNI / reverse proxy behavior without cutting off legitimate traffic.
2. Mitigate attack **upstream** when appropriate: edge rate limits/challenges and CDN/ISP/hosting-provider DDoS controls, coordinated with infrastructure operators who control upstream routing.
3. Triage source indicators: evaluate pre-collected 5-minute counters; differentiate attested edge logs, direct origin socket peers and unverified forwarded headers. IPs may be spoofed, proxied, NATed or shared; logs alone do NOT identify a responsible person or attacking machine.

**Never hack back, send counterattack traffic, scan the presumed attacker's machine, exfiltrate, or change someone else's infrastructure.**

## Code contracts

- `review_offline_evidence(engagement=..., evidence=..., verify_key=...)`
- `plan_origin_defense(engagement=..., traffic=..., verify_key=...)`

Both operate in memory without network I/O or writes. They require the *same* signed, expiring tenant/asset authorization. The canonical control plane must issue keys from its trusted secret store **only after verifying written authority**; signing a statement does not prove that authority was granted.

`plan_origin_defense` accepts `mojtaba.bot.ai.cyber.origin-defense.v1` observation records and returns **recommendations for review**. All actions have `approval_required=true`, `executed=false`, and no network or firewall calls. IP indicators are converted to scoped keyed tags to reduce sensitive data disclosure. Any `verified_edge_export` label remains unverified until the canonical collection pipeline provides cryptographic or equivalent provenance evidence.

Example invocation, within the canonical bot process only:

```python
from core.mojtaba_modules import registered_capabilities, plan_origin_defense
assert list(registered_capabilities()) == ["cyber_security"]
result = plan_origin_defense(
    engagement=signed_control_plane_manifest,
    traffic=authorized_offline_5_minute_counters,
    verify_key=trusted_key_from_secret_store,
)
```

## Integration and production acceptance gates (pending)

1. Attest the actual canonical bot process, dispatcher, identity/credential store and audit log on the intended hosts.
2. Register only `cyber_security` in that existing dispatcher, including its `origin_defense` function.
3. Establish signed authority from client and a fixed scope; add contract expiry, grant revocation, replay prevention, immutable event receipts and tenant isolation.
4. Attest collection of CDN/WAF/origin telemetry and trusted proxy chain. Treat untrusted `X-Forwarded-For` as unverified, not an IP banning source.
5. Provide authenticated, bounded, reversible **change plans** for edge WAF, host rules or ISP escalations, with explicit review, provider-specific validation, and rollback. Never apply automatically using only this model's heuristics.
6. Confirm VPS disk headroom, backups, emergency stop, deployment permissions, traffic baselines, allowed customer data retention and secure operations runbook.
7. Reuse current site's existing management/payment services; do not assume CDN/ISP paid products are subscribed, and incur no charges without owner approval.

For large volumetric DDoS, filtering purely on the origin host may be insufficient once upstream bandwidth is saturated. An ISP/CDN must provide the corresponding capacity and controls. Authenticated origin pull and a correctly configured ingress allowlist can reduce direct origin bypass but must be introduced carefully to avoid service outages.

## Verification

```bash
python -m unittest discover -s tests -p 'test_mojtaba_cyber_security.py' -v
python -m unittest discover -s tests -p 'test_mojtaba_origin_defense.py' -v
```

These unit tests have to pass before acceptance. CI-wide failures elsewhere are not evidence of this module passing or failing. The resulting offline module is **not** a live DDoS appliance, intrusion prevention system, autonomous attack mitigation deployment or proof of commercial readiness.

**Status:** Draft PR for code review. No new bot, no external scan, no live firewall/DNS/WAF changes, no deployment, no spending or customer billing.

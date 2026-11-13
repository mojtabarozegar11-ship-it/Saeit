# Mojtaba.bot.ai — Cyber Security capability (internal only)

## One bot rule

**Canonical bot:** `mojtaba.bot.ai` (immutable). **Capability ID:** `cyber_security`.

This is a Python module within the existing `core` package, **not** a second robot or assistant. Its file structure is:

```text
core/
  mojtaba_modules/
    __init__.py           # static canonical capability catalogue
    cyber_security.py     # offline security-evidence analysis
tests/
  test_mojtaba_cyber_security.py
```

No `Agent` model instance, second worker, daemon, cron job, independent scheduler, separate login, separate control plane, separate domain, or payment gateway must be created for this module. Never use the label `Mojtaba Cyber AI` to create another autonomous identity; it is only a marketing name for the security capability under the canonical bot.

## Executable scope (as committed)

- Local, memory-only analysis of **existing** security findings;
- Requires a signed, expiring authorization manifest issued by the **trusted canonical control plane**;
- Requires exact asset-hostname matching and tenant/engagement isolation;
- Returns severity counts, redacted findings and a SHA-256 audit digest;
- Cannot send requests to targets, enumerate ports, exploit systems, write data or execute subprocesses.

Example invocation (from the canonical bot process only, not a public endpoint):

```python
from core.mojtaba_modules import registered_capabilities, review_offline_evidence
assert registered_capabilities()["cyber_security"]["bot_id"] == "mojtaba.bot.ai"
report = review_offline_evidence(
    engagement=signed_control_plane_manifest,
    evidence=precollected_authorized_evidence,
    verify_key=trusted_key_from_secret_store,
)
```

The signature must be created by a separate trusted authorization component **inside the same canonical bot**, after checking the owner's/client's explicit permission and the authorized target inventory. Never expose the verifier key to a browser, website form or customer. Signing a scope is **not** proof that the system owner actually authorized it.

## Integration steps not yet executed

1. Confirm the canonical bot's deployed runtime, process and actual dispatcher; repository files alone do not prove live execution.
2. Register `cyber_security` as a named capability in the **existing** dispatcher, reusing its authentication, RBAC, task queue and audit log.
3. Introduce signed authorization storage, revocation, credential vault, anti-replay job IDs and per-tenant rate/resource budgets.
4. Load non-invasive evidence from approved collectors only; do not invent findings or claim to have performed live pentesting.
5. Reuse the existing dashboard and the existing company checkout and accounting system. Any `/cyber/` page is a **section** of the existing site, not a separate bot.
6. Validate backup, disk capacity, load, safety, isolation, legal scopes and independent review before production rollout.

## Production restrictions

Any active security assessment requires a signed statement of work, scope and written authorization; a tested stop/revocation mechanism; client isolation; rate limiting; and human sign-off on intrusive operations. Real targets and live customers must never be tested from a pull request. Security fixes and sensitive deployments require owner approval. Payments, external publication and expenses remain disabled unless individually authorized.

## Verification

```bash
python -m unittest tests.test_mojtaba_cyber_security -v
```

Tests establish limited offline behavior, not 24/7 protection, exploitation resistance, penetration-testing completion, business readiness or paid customer acquisition.

**Current status:** repository draft implementation for review; not merged, deployed, attached to a proven live dispatcher, or operationally scheduled.

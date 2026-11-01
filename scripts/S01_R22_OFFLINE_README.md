# S-01 R22 — Offline release evidence gates (2026-10-31)

Python 3.10+, standard library only. Read-only local-copy diagnostics; no network, SSH, VPS, cPanel, database, worker, payment, deployment or factory actions. Never pass live production files or secrets. Output omits source content and private paths.

Run from repository root:

```bash
python -m unittest scripts.test_s01_r22_offline_gates
python scripts/s01_r22_offline_gates.py checkout --current /absolute/observed.py --approved /absolute/approved.py --sha256 APPROVED_SHA256
python scripts/s01_r22_offline_gates.py office-stage --stage /absolute/local-stage --sha256 PACKAGE_TAR_SHA256
python scripts/s01_r22_offline_gates.py public-routes --evidence /absolute/authorized-observation.json
python scripts/s01_r22_offline_gates.py game-source --game /absolute/game.js --policy /absolute/moj1-commerce-policy.mjs
```

Synthetic offline test suite: 16/16 PASS, Python 3.13.5. Current file Git blob IDs: source `fb7fb5a11c11045d1edc06dd5273d5206da7410a`; tests `9e4844506d24199f7792a547a5178bb9ba4b1254`. Original local-only fixture result; CI run #41169341915 failed pytest collection on the former unqualified import. Commit 9e8195b8 corrects the import for repo-root pytest collection; verify the new exact-head CI before claiming green.

Scope:
- Checkout: pinned approved SHA; syntax and AST top-level drift classification; no source text in report.
- Zomorod office: archive SHA, extracted byte identity, special-member/symlink and unarchived executable guard.
- Zomorod public routes: offline evidence consistency against a blocked pre-release baseline, not an HTTP probe.
- G-01 handoff: source-only Ramadan game guard and MOJ1 disabled policy check, not browser/full ZIP verification.

**Current gates:** Checkout live source SHA differs from approved SHA; Passenger DB identity, full off-host restorable backup, invoice/payment/email/entitlement/download E2E remain unverified. Office #1666 draft and `deploy && false` safety block must remain unchanged; MFA/admin and rollback not verified. No live changes, merge or deploy. F-01 factory/master-agent HOLD remains absolute. OS shutdown not proven.

Private local ZIP `S01_R22_Offline_Release_Toolkit_20261031.zip` SHA256 `1b6c84b827dae4ab3473d5e664cea42f53eb88944f109be57874b9a772ae3dc2` was opened and checked. Library upload failed `container_session_unavailable`; the **source and tests in this branch are the durable recoverable output**, not the ZIP.

Refs: #1514, #1691, #1690, #1688, #1693.
# S-01 R23 — read-only auditable release gate (review only)

**Status:** DRAFT / CODE + SYNTHETIC QA. **RELEASE BLOCKED**. This change extends R22 on its own branch; it does not amend PR #1690 or #1691, change the live application, run the factory, merge, deploy, access a production DB, create an order, or send payment.

## Pinned source

- Parent PR: #1701 (head `ec5dd8977b41ab5f1c2a5f95a8e51218d50ccff3`).
- Related guarded changes: #1690 (office archive extraction), #1691 (checkout source ancestor symlink).
- Source and tests: `scripts/s01_r22_offline_gates.py`, `scripts/test_s01_r22_offline_gates.py`.

## R23 changes

1. Reject all unarchived files under the office source trees, including HTML and JS, not only executable extensions; reject symlinks.
2. Treat a public-route observation as attributable only when the exact Zomorod HTTPS origin, timezone-aware timestamp, 15-minute freshness, non-redirect evidence, and blocked baseline statuses are present.
3. Return exit code 2 for both `FORMAT_ONLY_DRIFT` and `BLOCKED_BASELINE_RECORDED`; they are diagnostic outcomes, **not** release passes.
4. Add `release-evidence` to report missing critical gates. Even if all flags are self-declared true, the result is `INDEPENDENT_ATTESTATION_REQUIRED` with `release_permitted=false` and exit code 2. Self-declared JSON can never authorize deployment.
5. Add nine synthetic regressions to the existing 16 R22 tests, targeting HTML/JS extras, stage ancestor symlink, old/forged public observation, missing redirect evidence, false-green CLI outcomes and absent/untrusted release evidence.

## Offline test commands

From a clean checkout of the **exact R23 head**, using Python 3.10+:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.test_s01_r22_offline_gates -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.test_s01_trx_rate_isolation_candidate -v
```

The tests use only generated fixtures in runner temporary directories; no live host or payment API is used. Before claiming CI green, record `git rev-parse HEAD`, run URL, tests collected/passed and file blob SHAs. Generic merge-ref CI does not by itself prove exact-head validation.

## Required independent release evidence (none supplied by these tests)

| Critical gate | Required authoritative evidence |
|---|---|
| Checkout source | Approved immutable SHA, exact observed source SHA, runtime code path |
| Passenger DB | Effective DB engine/name/host fingerprint derived from the actual Passenger process/configuration, without secrets |
| Durable off-host restore | Encrypted site **and effective DB** snapshot with externally stored checksum and verified isolated full restore receipt |
| Rollback | Immutable preimage, exact rollback procedure and verified isolated restoration receipt |
| Public routes | Fresh HTTPS, status, no-redirect and auth-protected route observation from controlled source |
| Buyer acceptance | Staging invoice, wallet return, receipt, entitlement, email and download acceptance; real purchase requires separate authorization |

**Policy:** all gates must be independently verified at the same intended release SHA; unknown/missing/failed evidence blocks. Existing #1666 deploy guard and factory F-01 HOLD must remain unchanged.

The original R22 `public-routes` diagnostic intentionally records a blocked baseline (404); this is not proof that the new office endpoints have been deployed or are ready. Code inspection and syntax validation are not substitutes for runtime acceptance.

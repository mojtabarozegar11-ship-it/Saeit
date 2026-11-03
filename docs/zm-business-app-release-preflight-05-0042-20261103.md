# Zomorod Melal — reconciled app guarded release workflow (05-0042)

Date: 2026-11-03. Scope: the private management/accounting desk at `/business/` only.

## Verified CI outcome

The workflow `.github/workflows/zm-business-app-reconciliation-release-20261103.yml` was committed as `6586c0821abc267d00ebcca4699c8cc57c350a6d`.

Its initial **push** run is [41571964258](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41571964258): **success**. This run is read-only with respect to the live host. It verified source and snapshot digest pins, PHP syntax, presence of named management integrations, pinned two-hop transport, current live-app digest/permissions, required accounting/project/governance tables, SQLite `quick_check`, and foreign keys. It did not deploy the reconciled app.

## Exact release contract

- Live pre-image app SHA-256: `ad9c80fc1bcff01c53cb58acabd088890e9f1dd0b7e3c38c95bd1ff4d67f27a7`.
- Review candidate SHA-256: `2ed9274affa87f3e9c51f7dff0c72d7461118c7aca0ae0ab732b1c81cbfd6005`.
- Baseline archive SHA-256: `7a8b2ab1dde07317c084646e4005ac843011821903f65b12297d283ee69412bd`; archive has only a known extra final LF.
- Candidate sources: `content/zomorod-business/app.php` and `app.reconciled-candidate-20261103.php`, required byte-equivalent.
- Only `workflow_dispatch` with `mode=publish` can execute the host-mutating release steps. The secret `ZM_APP_RELEASE_APPROVED_SHA256` must equal the fixed candidate digest. No claim is made that the secret is configured.
- Preflight verifies the exact live pre-image, native file permissions, compatible required tables, SQLite integrity and foreign keys.
- Publish mode creates an owner-only code backup and uses Python SQLite backup API for a consistent database snapshot in WAL mode.
- It transfers the pinned candidate and the source guard into a private stage, runs the guard against the live source and stored mirror, lints the candidate, then performs one atomic app replacement. On failed anonymous smoke or integrity check, it automatically restores the previous code from the private backup.
- The workflow does not create a financial, project, approval, employment or bank record. It does not send external messages or contact customers.

## Explicit limitations

A green preflight only shows source and infrastructure readiness, **not authenticated owner acceptance**, reliable financial operations or authorization of high-impact approvals.

The present `app.php` has not been deployed to production. Do not dispatch `mode=publish` until the source has undergone authorized management/accounting acceptance, the approval secret has been set through an authorized process, and a real independent reviewer is available for actions that require two-person control. No fake admin or fake accounting record may be created to satisfy a gate.

The older one-hunk `zm-banking-nav-live-20261102.yml` is a historical patch flow and is **not** the release vehicle for the merged app.

Next acceptance should cover actual login/logout, CSRF failures, role downgrades, project decisions with genuine evidence, period controls, invoices, journal corrections, assignments, reports, and all error boundaries, without touching live financial data while validating. This requires an authorized owner session or an independently authorized private acceptance environment; it has not occurred.

Final status: `NEW_RELEASE_PREFLIGHT=success`, `LIVE_APP_DEPLOYMENT=not_run`, `OWNER_AUTHENTICATED_ACCEPTANCE=pending`.

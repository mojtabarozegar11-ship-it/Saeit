# Mojtaba.bot.ai — read-only main-merge trigger impact (2026-11-16)

**Scope:** two cPanel-owned site-native agent fleets only. The central factory/VPS
is outside the authorized operational scope. Nothing in this document permits
remote execution, production deployment, switching Cron, paying, or deleting.

## Exact source evidence

- PR: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2533
- Whole workflow tree (before adding the new guard): 1,085 YML files at PR
  commit ddb44756; main was separately measured at 1,084. The new guard
  file took the PR checkout to 1,086. GitHub Contents directory listings
  truncate at 1,000 entries: use Git Trees or a **full checkout**, never that
  truncated list to claim full workflow coverage.
- New offline scanner: scripts/mojtaba_site_main_merge_impact_readonly.py
- New gate: .github/workflows/mojtaba-site-agent-main-merge-impact-readonly.yml
- The gate diffs the exact PR base/head with --no-renames, and scans the full
  checkout without SSH, secrets, GitHub API writes, or live site access.
- First actual gate run: 43910523933, job 133450865703; 1,086 YML files scanned;
  29 PR paths compared; 11 tests passed; 9 initial conservative possible
  triggers and 0 unknown syntax. The deliberate exit code 3 was **NO_GO**,
  not a failing code test.

## Nine initial candidate triggers (before causal graph refinement)

| Workflow | Source mechanism | Independent source finding |
|---|---|---|
| ci.yml | main push, unfiltered | Reviewed offline test-only workflow |
| django-ci.yml | main push, unfiltered | Reviewed offline test-only workflow |
| zomorod-app-pages-deploy.yml | push with command_center/*.py | Publish job requires workflow_dispatch, not push |
| atelier-interior-native-draft-after-restore-20261021.yml | workflow_run | Pinned historical run ID and SHA; separate upstream |
| comfyui-phone-receipt-auto-authorize.yml | workflow_run | Restricted to a named feature branch; not main |
| factory-f26-guard-readonly-20261022.yml | workflow_run | Named F26 upstream; not the changed PR CI |
| factory-native-moj1ro1-handoff-20261022.yml | workflow_run | Named native candidates upstream |
| factory-toolchain-resume.yml | workflow_run | Named private toolchain upstream; contains VPS actions |
| mojplaywin-backup-and-restore-onepass-20261017.yml | workflow_run | Pinned historical backup run ID and SHA |

The refined source scanner follows named workflow_run dependencies from the
main-push candidate set and respects non-main branch filters. Reviewed
byte-identical CI/manual-publish files are pinned by Git blob hashes; changing
their contents invalidates the exemption. This is a **static conservative audit**:
manual or dynamically invoked workflows and production side effects not caused
by this merge require their own safety checks.

## Release and retirement gates remain separate

1. An offline gate result of REVIEW_REQUIRED/zero unreviewed triggers only
   resolves the merge-trigger dimension; it **never** sets merge_authorized,
   deployment_authorized, or host_cleanup_authorized to true.
2. Re-check exact-head CI, Django migrations, and code security before making
   the PR ready. CI cannot attest DNS/TLS, cPanel runtime identity or
   production behavior.
3. Before site cutover, independently attest the canonical bot on both live
   tenants; private staff UI parity; two distinct site receipts; real process
   ownership; private SQLite and history parity; off-host restore; and
   rollback. Do not mistake 77 module slots for 77 migrated workers.
4. Inventory exact old file hashes and both old Cron markers using a
   read-only, authorized cPanel path; no relay to central VPS.
5. Retire precisely pinned obsolete files only in a separate,
   recovery-backed operation **after** replacement and all owner/legal
   controls, never by deleting parent or root private folders.
6. Preserve payment/TRON/order/customer evidence and isolated histories.

**Current host facts:** zero verified removed files; zero verified Cron changes;
zero verified reclaimed bytes; zero new expenses; no live host deployment in
this PR. Draft remains the correct state until other gates are proven.

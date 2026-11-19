# MojPlayWin release checkpoint — 2026-11-19
## Evidence
- Owner-local backup audit 44534612423: separate store-code and mail archives verified. Database backup and full restore remain unproven. No Google Drive.
- 44542940944: candidate RPC in memory, both previous paid receipts independently observed at two endpoints; both match invoice; 2 stored grants and private files. No new transaction, delivery or production replacement. Operator infrastructure attestation remains separate.
- PublicNode TRON gateway identifies Allnodes: https://tron.publicnode.com/ ; TronGrid official interface: https://developers.tron.network/docs/trongrid ; public usage/reliability limits: https://developers.tron.network/reference/rate-limits. No paid plan authorized. Successful anonymous calls do not guarantee production quota.
## Release boundary
1. Verify pinned current main and candidate source; do not replace unrelated project files.
2. Identify exact public WSGI worker, compare runtime hashes; CLI presence alone is not public deployment proof.
3. Preserve local store/email backup, separate from factory. Establish local database backup/restore before database changes; do not copy a shared company database blindly or publish customer data.
4. Obtain explicit release approval for merge/deployment, and separately for sending purchase recovery email where required. Keep payment admission flags false until verified operator identity, runtime candidate, applicable rate limits, release and delivery controls are satisfied.
5. Install only reviewed source with atomic rollback; maintain existing paid download access. Never change the receiving wallet, old receipts, existing grants, theme, or factory as part of release.
6. Verify public HTTPS GETs, concrete products, valid email form, disabled-wallet guest path, exact native TRX invoice; no test financial transaction without authorization.
7. Configure bounded host scheduler for existing invoices, retaining and cycling cursor; no Actions dependency in operational checkout. Verify local scheduler and recovery email delivery before marking commercial ready.
8. Measure actual new paid orders and receipts; no readiness percentage inferred from CI.

## Owner-local scheduler package
After approval and installation of the exact reviewed source, run the script from the cPanel account every five minutes using the existing Python interpreter: 
`*/5 * * * * /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python -B /home/zomorod2/Saeit-staging/scripts/mpw_reconcile_scheduler.py`
The wrapper locks its private state, advances in batches of three, wraps at the end, and leaves the cursor unchanged after a failed run. The existing management command still requires the settlement and provider gates. Do not install this schedule before approval. The current command looks back seven days; older unresolved payments need owner review and must not be marked expired/paid by this runner.

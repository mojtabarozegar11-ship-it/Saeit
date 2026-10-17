# MojPlayWin — full recovery and runtime separation gate

**Status: NO-GO.** This runbook is NOT evidence of a completed backup, test restore, or isolated release. Preserve *every* MojPlayWin child site, including unknown ones. Never restart shared Passenger.

## Mandatory execution order

1. **Preserve the freeze.** Keep all three historic auto-deployment jobs locked and block publishing PR #390. Audit external CI/CD, cPanel cron, and other possible production writers. Require GitHub protected-main branch rulesets; the source-only CI guard cannot prevent a user from force-pushing or merging when main is unprotected.
2. **Inventory all tenants and routes.** Reconcile cPanel Domains, Apache vhosts and rewrite conditions, Passenger roots, WSGI entrypoints, Django routes/middleware, filesystem aliases and symlinks. Include undiscovered subsite roots before selecting paths for any backup or deployment.
3. **Confirm effective production DB engine without exposing secrets.** The source code loads DATABASE_URL and otherwise defaults to SQLite. Verify the actual runtime engine and connection using an authorized operator; never print a full DATABASE_URL or query user data in public logs. For SQLite, account for WAL; for PostgreSQL/MySQL use transaction-consistent backup methods.
4. **Capture a complete encrypted off-host snapshot.** Include database(s), all physical and dynamic child sites, Media and user uploads, code, config, URL rewrite/Passenger declarations, payment/order records, and secret configuration only in access-controlled encrypted storage. File-copying a live SQLite database in WAL mode is NOT sufficient. Record hashes and version/time and independently verify archive readability.
5. **Restore in a different runtime with isolated resources.** Independent host or restricted container, own DB, application root, identity and virtual environment. Disable email, production webhook delivery, scheduled tasks, payments, external API posting and queue consumers. No production secrets or live DB connection. Test product/order counts, original article/page totals, site media integrity, admin/test login and routes.
6. **Prove main-only deployment at infrastructure level.** An independent GitHub workflow does NOT create isolation. Prove that app root, DB, WSGI/Passenger worker, public URL routing and rollback do not mutate, reload or intercept any protected child site. Baseline every inventoried subsite and compare pre/post.
7. **Release only with reviewed 19/19 evidence and explicit approval.** Keep PR #390 draft until every gate is individually verified; old rollback scripts that touch shared Passenger are forbidden.

## Evidence known on 17 October 2026

- Production WSGI still points to shared Saeit-staging; no isolated main-only deploy is proven.
- Twenty-four old deployment manifests exist; none reference DB or Media backup paths, and a successful full restore is NOT evidenced.
- cPanel Backup UAPI returned zero entries; provider-managed/offsite backups may still exist.
- Eleven named public GET endpoints returned HTTP 200; unknown sites, login, article inventories, checkout, payment and data integrity remain unverified.
- GitHub main had no mandatory branch protection at last inspection.

## Release blocker register

| Item | Required proof | Current status |
| --- | --- | --- |
| Effective DB backend | Authorized safe identification, no secret disclosure | NOT VERIFIED |
| All child roots/routes | Full Apache/Passenger/Django/cPanel inventory | NOT VERIFIED |
| Complete backup | Consistent DB + Media + code + config + every subsite | NOT VERIFIED |
| Encrypted offsite copy | Verified manifest, integrity hashes, secure retrieval | NOT VERIFIED |
| Restore rehearsal | Full isolated recovery and application smoke tests | NOT VERIFIED |
| Data/commerce invariants | Products, orders, ETH/TRX payment integrity | NOT VERIFIED |
| Independent main runtime | No shared Passenger restart or child write | NOT VERIFIED |
| Mandatory GitHub main protection | Branch rulesets, approvals, required checks | NOT VERIFIED |
| 19/19 release evidence | Independent reviewed evidence for every dimension | NOT VERIFIED |

**Sensitive materials—.env, API keys, database credentials, user records, uploaded media and backup archives—must never be printed into public GitHub Actions logs or committed to the repository.**

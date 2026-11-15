# Moj Prop commercial schema migration runbook — 0042–0045

**Owner rule:** no automatic release, no spending, no invoices or real wallet operations without separate authorization. This runbook is a release prerequisite, NOT a deployment approval. The current legacy backend installer deliberately refuses a commercial schema upgrade.

## Verified source scope
- Existing production-style public intake schema: `0041_mojprop_request`.
- New sequential migrations: `0042_mojprop_offer`, `0043_mojprop_digital_inquiry`, `0044_mojprop_acceptance_evidence`, `0045_mojprop_delivery_evidence`.
- Application models include MojPropOffer/MojPropDeliveryEvidence; do not copy new models without migrations.
- `/moj-prop-intake/` and `/moj-prop-status/` must remain live and preserve signed bearer receipt privacy.
- New `/moj-prop-quote/<token>/` must not appear in Apache's static /moj-prop/ directory. Default `MOJPROP_PUBLIC_QUOTES_ENABLED=False`.
- Never treat manually reviewed, issued, or accepted quotes as settled money. Delivery evidence requires an actual linked accepted offer, separately verified clearance and delivery.

## Source-only checks (no production access)
```sh
python3 -m unittest tests.test_mojprop_db_release_evidence_20261115 tests.test_mojprop_legacy_backend_upgrade_gate tests.test_mojprop_commercial_release_preflight_20261115 -v
python3 scripts/mojprop_commercial_release_preflight.py --repo-root .
python3 manage.py check --deploy
python3 manage.py makemigrations --check --dry-run
```
Success means source is internally consistent, **not** that the live DB is backed up or that new migrations have been deployed.

## Mandatory runtime release prerequisites
1. Identify pinned Passenger application root, Django runtime, *actual* DB server/name and application database user without printing passwords. Confirm the same effective app serves the Moj Prop intake and quote routes. Do not infer production from HTTP 200.
2. Verify available disk space **before any backup**; archive must be private, integrity-checked, and stored outside document root. If capacity is insufficient, block; never delete unknown production files to free space.
3. Obtain a **complete, transactionally consistent production DB snapshot** including schema, tables, triggers and migrations. Encrypt the backup according to the operator's data-protection requirements; do not put the dump or secrets into GitHub.
4. Independently restore the exact snapshot into a **different isolated non-production DB**. Verify counts and checksums on core tables, database character set/collation and sample relationship constraints. Record auditor identity and a real SHA256 of the snapshot. An operator must verify restore success; a Boolean field alone is not proof.
5. Supply a run/commit/DB-identity-bound HMAC verification receipt in a private location, with key delivered through a separate secret channel. `scripts/mojprop_db_release_evidence.py` checks SHA256, HMAC, run identity, isolated target, permissions and a 24-hour proof window. **It cannot itself prove the operator actually performed the restore.**
6. Review `sqlmigrate core 0042`, `0043`, `0044`, `0045` against the actual live backend. On MySQL/MariaDB, some schema DDL can auto-commit and is not fully rollback-safe. No file-only rollback may be described as DB rollback.
7. Confirm no parallel writes from other automated cycles during migration. Record a maintenance/locking plan, approved outage window and actual operator recovery access.
8. Use an independently reviewed **new schema-aware deployer**, not `deploy_mojplaywin_moj_prop_backend.py deploy`. The old deployer only copies `0041` and is now intentionally blocked.
9. In staging, rehearse both the forward migration (0041→0045) and a failure-path **database restore + files/URLconf/Passenger recovery** from the same snapshot. Prove restored read/write operations and existing buyer receipts work. Save evidence privately.
10. Only after every above gate and a separate owner approval, execute controlled production migration using the authorized channel, then smoke-check new route, logged-out 404 privacy, quoted acceptance immutability, and existing buyer/status flows. Enable public quote sharing **separately**, after legal/customer notice review.
11. If any step fails, preserve the failure and stop irreversible operations. Restore DB and app as **one coherent version** using tested tooling. Do not rely on `restore()` in the legacy installer: it restores only files.
12. Keep real TRON receiving, email, invoice and live trading disabled until their **separate** wallet, customer-consent, settlement and regulatory gates pass.

## Machine-readable gate command
The source-only command performs static checks and intentionally returns `production_release_ready: false`. To validate a private rehearsal:
```sh
MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY='<provided via protected secret manager>' \
python3 scripts/mojprop_commercial_release_preflight.py --repo-root . \
 --verify-release --backup-root /private/isolated-mojprop-db-evidence \
 --run-id '<unique-run-id>' --commit '<40-char-reviewed-commit>' \
 --database-identity-sha256 '<sha256-of-actual-runtime-DB-identity>'
```
Do not store the literal key in shell history. The command itself **does not** run migrations or activate a merchant. Its successful exit is not full production authorization.

## Explicit revenue blocker status (at time of source audit)
- Core Prop commercial schema merged to `main`, but live schema migration **unverified**.
- Buyer written offer and delivery evidence schema exist in source; no production-backed order, payment or delivery proven by this check.
- Correct gate sequence: verified lead → written reviewed offer → lawful agreement → independently confirmed payment/credit clearance → documented deliverable → customer acknowledgment, without treating any earlier state as paid.

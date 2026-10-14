# MojPlayWin factory telemetry and product handoff — verified 2026-10-14

## Evidence-based state (do not collapse independent stages)

1. **VPS process:** `factory-runtime/operations/vps-only-loop.sh` was observed with exactly one matching PID/process. The activity log was recently updated; this does **not** prove new products or successful jobs. [Runtime audit](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38585104797).
2. **Private manufacturing:** the autonomous product-cycle state reported 25 candidates, 25 dossier updates, 2 private packages, technical QA passed, `publishable_product_count: 0`, `store_distribution_state: not_connected`. This is the producer's state record, not the receiving system's live status. [Cycle audit](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38585641893).
3. **Receiving-system evidence:** a successful separate product-handoff workflow reported `factory_store_transfer_count: 2`, one `already_received`, one `received_private`, with `public_listing_enabled: false`. Thus private delivery occurred, even though the producer state retained `store_distribution_state: not_connected`. [Private handoff run](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38571122351).
4. **Public catalog and paid sales:** Neither proof of public listings nor proof of live settled checkout follows from private handoff. Confirm receiving inbox manifests, product completeness, classification, ownership and public release gate before enabling listing.

## Telemetry contract prepared but not deployed

- `scripts/mpw_factory_telemetry_sample.py`: collects bounded non-secret numeric VPS observations, no mutation.
- `scripts/mpw_factory_telemetry_receive.py`: validates exact schema, age and type then writes a 0600 private file under the cPanel account.
- `command_center/factory_status.py`: reads the private file with same-owner/freshness checks; does not claim sales.
- `command_center/evidence_metrics.py` and `dashboard.html`: expose sampled runtime separately from financial metrics.
- Isolated CI tests verify missing, malformed, stale and spoofed status, plus sender-receiver-reader roundtrip.
- **Bridge workflow not installed**: attempted creation was refused by tool security controls. Do not imply continuous live status; no production dashboard changes have been deployed in this feature branch.
- To complete, obtain authorized secure transport from VPS to cPanel (ideally reuse the existing factory-to-private-inbox channel with a constrained non-secret status payload), verify delivery and freshness, then use a guarded release with backups and rollback. Do not alter the existing live factory loop, public site, bank/payment settings or publish products merely because private QA passed.

## Operational cautions

- A live loop PID alone cannot prove effective manufacturing. Error counts and product state need independent checks.
- The receiving private inbox already had 2 handoff receipts; avoid describing the **entire** VPS-to-cPanel private delivery as disconnected.
- There are two distinct data stores (VPS SQLite and active cPanel MySQL); do not combine their task/product counts into a single total.
- Revenue remains **unknown** without independent merchant settlement evidence.

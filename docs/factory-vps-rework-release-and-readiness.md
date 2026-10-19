# VPS Factory: non-discarding technical and research QA rework

## New verified code paths
- Existing scheduled factory makes real working ZIPs from two tested calculators.
- Failing recipe QA leaves the previous archive unchanged, records a durable
  private defect with code, observed symptom, corrective action, source version
  and attempt count, and permits other unrelated recipes to continue.
- Identical failures do not create duplicate issues each hour. A third distinct
  failing source revision escalates to expert help, not deletion.
- A correction counts as *technical recovery only* after rebuilding with real
  tests and a recorded ZIP SHA256 checksum.
- Failed research quality gates create individual, durable research-defect
  tickets with unmet evidence/ownership requirements and correction plans.
- The private store sender rejects transfer of stale ZIPs when an active
  rework ticket exists.
- No automatic sale, API charge, database migration, cPanel edit, product
  approval, user-facing store publication or bypass of research requirements.

## Honest state distinction
Technical QA passed is NOT commercial approval. Research evidence counts are
not proven validity. The private staging ZIP is not a listed retail product.
The factory currently sets publishable_product_count to zero until proper
owner, license, validated market evidence, commercial QA, checkout and delivery.

The separate four-source manufacturing intake and Django owner/rework UI
in PR #502 must be reviewed and safely deployed independently.

## Tests
- python3 -m unittest discover -s tests -p 'test_factory_product_rework.py' -v
- python3 -m unittest discover -s tests -p 'test_factory_vps_product_cycle.py' -v
- python3 -m unittest discover -s tests -p 'test_factory_product_maker.py' -v
- python3 -m unittest discover -s tests -p 'test_store_bridge.py' -v
- bash -n deploy/install_autonomous_factory_products.sh

## Live installation — not automatic
The existing GitHub Action "VPS Autonomous Factory Product Install" is
workflow_dispatch only. On the verified main branch it stages approved scripts
via pinned SSH. Confirm a tested backup, active service, adequate disk space
and exact production site isolation BEFORE a manually authorized installation.
Verify that existing hourly cron has exactly one autonomous product entry
and that the main VPS factory loop remains alive.

No checkout or final product publication is triggered by this deployment.
The private product sender must also be upgraded to the protected revision
before any rework-blocked private package handoff is allowed.

## Outstanding blockers
1. Verified product owner and research provenance on 95 blocked tasks.
2. Authentic evidence and research fixes for the factory's draft products.
3. Four-origin manufacturing orders with independently authorized VPS jobs.
4. Commercial product files, rights, acceptance tests and owner release.
5. Correct MojPlayWin production database and tested backup before Django
   migrations, store integration or customer payment/fulfillment tests.

Do not claim a factory is selling until those tests are evidenced.

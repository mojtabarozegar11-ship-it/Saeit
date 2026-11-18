# MOJ PROP real 30 native TRX — production readiness request

Owner states on 2026-11-18 that a relevant authorization has been issued and explicitly requests activation of real collections. The owner does **not** consent to sharing permit images or identifiers in GitHub. This file contains no permit data, wallet private keys, personal IDs, or paid transactions.

**Purpose:** force one GitHub Actions read-only live check of whether the existing cPanel/VPS/private backup/restore infrastructure can support an actual safe real-money launch. The user authorizes activation in principle; this file is NOT proof that publication prerequisites are met and is NOT itself a deployment.

**Operational truth to verify (do not assert from source CI):**
1. Pinned cPanel SSH authenticates to correct account, with actual MojPlayWin application root and runtime.
2. Existing current MariaDB/customer files and media have independent offsite encrypted backup and successful restore evidence; live database capacity sufficient.
3. VPS/relay host pin and connectivity work, without sensitive output.
4. Current root URL mapping and the intended MOJ-PROP-01 checkout are isolated; no overwrite of existing services.
5. All legacy native TRX product writers share a single deduplicated settlement ledger with a backfilled history before enabling any new 30 TRX invoices.
6. Production deploy scripts, release paths, rollback and cron schedule are available and reviewed; no production changes may be attempted by this read-only workflow.
7. No externally issued license data or legal compliance conclusions are implied by the owner's assertion; confidential check is performed only outside source control.

**Why needed:** Source PR #2700 had 939 successful isolated tests in Actions #44188696824, but LIVE `/moj-prop-v141-info/` returned 404 and the current main branch lacks the underlying `prop_firm` backend entirely. Preventing unfulfilled paid customer orders requires proof of live installation, not test success. 

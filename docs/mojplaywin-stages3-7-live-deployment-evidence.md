# MojPlayWin commercial deployment evidence — stages 3 to 7

**Date:** 2026-10-15, based on GitHub Actions runs from 2026-10-14 UTC.

## Current production truth

**DISABLED INSTALLED / NO CUSTOMER PAYMENT RELEASE**.

The MojPlayWin production Django runtime on cPanel now has the
`mpw_commerce` package physically installed and registered as an
`INSTALLED_APPS` entry through an append-only addition to the existing
`config/settings.py`. Migrations `0001_initial` and
`0002_buyerwalletchallenge` were applied to the live shared MySQL
database and create four new commerce tables. All nine commerce feature
switches are explicitly **False**. No commerce URL is exposed; the
public `/checkout/` route still returns **404**.

After the change, the homepage and `/store/` returned HTTP 200.
The independent read-only confirmation reports:

- `mpw_commerce` present and registered: **true**
- migrations 0001 and 0002: **applied**
- invoice URL resolved in live config: **false**
- active Product records in shared Django catalog: **0**
- Order records and PaymentIntent records: **0**
- CommerceInvoice / CommerceReceipt / CommerceFulfillment rows: **0**
- shared Product records: **193** at the time of final read-only scan
  (earlier snapshots had 190 and 192; ongoing separate factory work may
  change that count; these are not MojPlayWin-only sales totals).

## Evidence and exact sequence

| Stage | Verified result | Evidence |
|---|---|---|
| 3: private shadow | Exact current code passed Django checks, migration plan and shadow-only invoice route test, with all flags off | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655935683 |
| 3b: fresh restored DB | Current private candidate's two migrations succeeded on clone of real host MySQL snapshot, four tables added only to disposable DB | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656067065 |
| 4: inert package | Installed source files only, not registered, no DB changes; homepage/store 200, checkout 404 | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656387957 |
| 4b: independent scan | Live inactive package, all gates still off, no orders | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656547391 |
| 5: independent VPS backup | Streamed encrypted SQL backup onto separate VPS with private key and compared full decrypted SHA256 to original cPanel archive; no plaintext backup saved in GitHub Actions | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656683238 |
| 6: disabled Django registration | App registered via guarded append-only settings patch; two migrations on live MySQL; four commerce tables; all payment flags false, homepage and store healthy, checkout still blocked | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38656938893 |
| 7: independent final audit | Registered app and migrations confirmed; invoice route absent; commerce tables empty, no sales | https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38657047834 |

### Earlier safeguards

- On-host fresh private SQL dump with SHA256 and code snapshots:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655256296
- Verified 86-table restore and deletion of temporary DB/user:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655380848
- Scoped migration plan tested on restored source DB:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655548580
- Drift detection: four of six shared live Python paths differ from
  release; no full-file wholesale overwrite:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38655333323
- 68/68 isolated purchase, refund-resistant security, ledger,
  private-delivery and course activation CI tests passed on MySQL 8.
  These use simulated blockchain receipts:
  https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38654218472

## Exactly what is not live

1. **No real payment verification or settlement** and no receipt of buyer
   funds tested against an actual authorized mainnet purchase.
2. **No public paid checkout or invoice route**, and no commerce feature
   switch enabled. The old sitewide `/checkout/` still returns 404.
3. **No published sale products** in the shared Django catalog. Recorded
   files or prices are not approval for sale.
4. Merchant control of public ETH and TRX receiving addresses has not
   been independently proven by owner-signed nonspending wallet messages.
5. Buyer rights, source originality and fair price review, refund support
   and automatic private delivery on the *live* runtime remain pending.

Do not invent paid revenue, manufacturer quality or a prior crossed-out
price. The new schema is empty; a green CI pipeline is **not** revenue.


## Independent final catalog eligibility check

Read-only evidence: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38657266642 .

- 193 shared-catalog products; 193 with nonempty metadata and titles of at least 20 characters. Neither measure is a content-quality certification.
- **Only two priced USD products (IDs 72 and 147)** and **zero active**.
- Two products have an assigned owner; **none** have a linked research article.
- **Zero** have the structured `mpw_commerce` sale policy, a configured private asset under that policy, or `enabled=true`.
- Zero have `factory_publication_permission=true`, `asset_verified=true`, `quality_approved=true` or `license_verified=true` in the checked metadata fields. Different undocumented keys could exist; these results are not proof that no rights documents exist elsewhere.
- Therefore the catalog **cannot** be safely bulk-published; there is no product with independently evidenced sale eligibility in these known checks. Product bytes, authorship and market pricing require separate substantive evaluation.

## Production rollback and final release policy

**Live app settings:** app registration is introduced only inside
`# MPW_STAGE6_DISABLED_COMMERCE_BEGIN` /
`# MPW_STAGE6_DISABLED_COMMERCE_END` at the end of
`config/settings.py`; all switches are False. The original settings
file, separately verified via SHA256, is privately stored under the
timestamped backup's `source-rollback/config/settings.py`.
It can be restored atomically only after checking nothing else changed
since the patch. Doing so unregisters `mpw_commerce` without touching
customers' business data. Do not blindly overwrite live settings.

**Schema:** four *new* commerce tables currently contain no real
transactions. Do not automatically drop them in rollback; preserve them
as inert until any possible concurrent writes are ruled out.

**VPS disaster recovery:** the independent VPS copy is encrypted at
rest and its decryption key is held privately **on that same VPS**.
It is a separate-host copy, not an independently managed external key
escrow or an immutable/offline backup. For full disaster recovery,
a separately controlled key and tested recovery procedure remain
advisable. No customer data or private .env was uploaded to GitHub.

Before enabling a public Buy button, separately verify approved
merchandise, wallet control, finalized real-chain settlement and
one authenticated customer-to-entitlement flow on a safe staging
equivalent. Publish routes via a reviewed minimal diff only after a
controlled release decision and rollback smoke plan.

**Current release decision:** Infrastructure deployment complete,
**public sales NO-GO**. This is an explicit security control, not an
unreported or failed payment activation.

# MOJ PROP: live acquisition, source provenance and backup NO-GO (2026-11-17)

Status: **READ-ONLY AUDIT ONLY** — no deployment, order, payment, backup creation,
SQL migration, SSH fingerprint override or customer contact. This is a
source-only stacked Draft under #2693 -> #2690 -> #2688 -> #2684.
All proposed buyer terms are unaccepted DRAFTs. The contract has **one global
28-day simulation evaluation deadline** shared by the two sequential phases.

## Public website: observed from an external GitHub Actions runner

| Route / method | Observed status | Evidence / interpretation |
| --- | --- | --- |
| `HEAD https://mojplaywin.com/` | 200, TLS verify OK | Public site answers, not proof of sales |
| `HEAD https://mojplaywin.com/moj-prop/` | 200, TLS verify OK | Apache's public legacy product surface is served |
| `HEAD https://mojplaywin.com/moj-prop-v141-info/` | 404, TLS verify OK | v1.4.1 information page not served at this path |
| `GET /moj-prop-interest/form/` (EN) | 404 | New v1.2/1.4 Plan1 consent form absent from live |
| `GET /moj-prop-interest/form/?lang=fa` (FA) | 404 | Farsi consent form absent |
| `GET /moj-prop-intake/?format=html&service=blueprint&package=moj-prop-01` | 200 but NO validated native secure form | Status 200 is **not** a working paid or unpaid lead capture |
| `GET /moj-prop-status/?format=html` | 404 | Proposed private manual-review receipt lookup not live |

Exact receipts: [#44162424645](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44162424645)
and [#44162993320](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44162993320).
The latter verified **24/24 backup/code** and **13/13 mainline intake**
synthetic checks; **19/19 independent new-consent synthetic** checks also
passed, but *all real GET acquisition-route checks failed*. A unit test
passing does NOT override the observed HTTP result.

The current `main` branch contains `core/mojprop_views.py` with
`mojprop_intake`, `mojprop_receipt_status` and the non-JS
`core/mojprop_accessible_intake.py`. It defines a prospective `MOJ-PROP-01`
nonpayable written-offer inquiry prefill under
`/moj-prop-intake/?format=html&service=blueprint&package=moj-prop-01`.
It is not a customer account enrollment or TRX payment. Since the live GET
did not show the required form, **source existence is not production evidence**.

## Live server inventory / remote access

- Exact SSH fingerprints previously pinned in vetted workflows remain
  mandatory; never disable strict verification to reach cPanel or VPS.
- GitHub runner's direct cPanel `178.239.147.125:1396` key-scan and
  historical VPS `178.239.147.150:22` key-scan both failed.
  Classified **HOST_KEY_UNREACHABLE_OR_MISMATCH**; do not assert that the
  fingerprint definitively changed. No SSH authentication or production
  file/SQL scan occurred in these runs.
- The updated audit workflow independently checks both hosts even if one
  fails, and additionally reports DNS/TCP socket reachability on the
  previously authorized addresses to distinguish *network failure* from
  an observed cryptographic identity mismatch.
- Historic account disk usage and VPS free space must not be restated as
  currently confirmed. Read-only live sizes must be obtained after
  restoring secure authenticated connectivity.

## Off-host backup: explicit prerequisites for a safe release

A preinstalled owner-armed and **main-only** restore workflow
`.github/workflows/mpw-fresh-primary-backup-isolated-restore-20261101.yml`
exists. It needs exact `BACKUP_AND_ISOLATED_RESTORE` dispatch confirmation,
an authenticated pinned cPanel/VPS relay, sufficient private GPG capacity,
a pre-existing recovery key, consistent source identity, both encrypted
SQL and scoped files, a verified manifest, independent isolated
decryption/restoration and all external media coverage. It is **not
authorized or triggered** by this audit.

Two new read-only sources in #2693:
`scripts/mojprop_v141_offhost_pair_metadata_readonly.py` (private
manifest/ciphertext *metadata only*, refuses to infer restore) and
`scripts/mojprop_v141_live_code_presence_readonly.py` (source code
fingerprints from a **candidate** Passenger tree). Neither reads customer
files, GPG key, database rows or changes host state. Their purpose is to
avoid green source-only CI masking actual missing recovery evidence.

Current external Google Drive `MojPlayWin-Private-Backups` folders named
`database`, `site-files`, and `integrity-manifests` showed no files in
the first connected account; this is **not** proof that all backup storage
across all accounts/hosts is empty. A full current DB+media recovery is
still not verified.

## Release dependencies — minimal safe operational order

1. Recover **read-only** authenticated inventory via already pinned
   GitHub→VPS→cPanel relay or verified provider portal. Resolve network
   ingress/port routing without trusting an unverified host key.
2. Identify actual Passenger/Wsgi deployment root and its complete
   source commit fingerprint; compare against the currently served URL
   map. Do not assume `Saeit-staging` is effective.
3. Establish fresh, full site+DB+media encrypted off-host backups and
   independent *isolated restoration*. Explicit owner-approved workflow
   only; prove adequate destination disk and source transactional snapshot.
4. Reconcile production schema, 0009/0010 migration plan, rollback and
   tenant ownership; **do not** apply migrations before restore rehearsal.
5. Prepare a legally reviewed **unpaid** customer inquiry form on the
   correct root-level Apache/Passenger mapping. In production, verify
   real GET, CSRF and session with **authorized, genuine customer**
   submissions; never fabricate a buyer or send unsolicited outreach.
6. Add independently authenticated and archived XAUUSD market
   fills/equity/day-open snapshots, not just internal HMAC.
7. Confirm legal jurisdictions, signed buyer terms, KYC, AML/refunds,
   broker permission and company capital. Only afterward seek separate
   owner approval for 30 native TRX payment, qualified enrollment,
   actual execution and public launch.

**Current gate verdict: NO_GO_CUSTOMER_ACQUISITION; NO_GO_PRODUCTION_RELEASE;
NO_GO_PAID_CHECKOUT; NO_GO_LIVE_BROKER_EXECUTION.**

# MojPlayWin private inquiry desk — operating contract (2026-11-14)

**Status: committed to an integration/Draft branch only. NOT deployed to cPanel; no customer lead has been read by this work.** This is a subordinate read-only reporting component for the *single* organizational agent `mojtaba.bot.ai`, not a second bot, inbox, CRM subscription, payment service or order processor.

## Revenue blocker and existing production source

The existing first-party inquiry handler `mpw_revenue_20261020/earn/inquiry.php` stores accepted leads outside the public web directory, at `/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries`. Records use authenticated AES-256-GCM envelope version 1 and a private 32-byte `.inquiry-key`. The existing `scripts/mpw_revenue_owner_inquiry_dispatch_20261026.php` can submit owner notifications to a local MTA, **but queuing a notification is NOT proof that the owner received it, that the customer was contacted, or that a sale was made**.

The new `scripts/mpw_revenue_owner_inquiries_readonly_20261114.php` solves a distinct need: private, bounded, read-only lead triage and backlog reconciliation **without invoking that dispatch tool or sending any email**.

## Commands — ONLY once separately reviewed and made available to the authorized cPanel CLI

```sh
php scripts/mpw_revenue_owner_inquiries_readonly_20261114.php summary
php scripts/mpw_revenue_owner_inquiries_readonly_20261114.php summary 2
php scripts/mpw_revenue_owner_inquiries_readonly_20261114.php inspect ABCDEF0123456789AB
```

These commands are *examples*, not evidence of deployment or permission to change production. The `inspect` reference is synthetic. Real references are unpredictable 18-character hexadecimal IDs from the private inquiry filenames. The script must run under the designated `zomorod2` OS account (except isolated fixtures); it aborts in GitHub Actions and if the key, private directory, file or ownership boundary is not suitable. The host must have PHP CLI with OpenSSL and compatible permissions. The script never changes inquiry files, writes logs, sends email, requests payment, creates an order or modifies an account.

## Interpreting fields without misleading commercial claims

- `total_files` counts matching encrypted filenames, not verified customers; `valid` is the number of AEAD-decryptable records with valid source/consent, recognised service slug and email syntax *on the selected page*. It is not proof of mailbox ownership.
- `page`, `total_pages`, `scanned`, `backlog_truncated`: newest-first pages of 500; use `summary 2`, `summary 3` and so on to examine older records if needed.
- `by_service` counts verified-format, consented inquiry records by existing catalogue slug on this page. Treat as **possible sales opportunities**, not booked orders or revenue.
- `not_yet_notified`: no valid owner-dispatch marker was seen. `notified_to_local_mta`: a valid-looking marker exists; it does **not** establish successful inbox delivery.
- `pending_references`: up to 25 pseudonymous reference codes, with `pending_refs_truncated` when more remain. **No personal email, name, project text, token, secret or payment address** appears in the machine output.
- `older_than_24h` and `older_than_72h`: age of records on the selected page, not dates of contact attempts.
- `inspect REF` returns redacted metadata only. Contact details remain encrypted at rest. `quote_sent` remains `unknown`; `payment_received` remains `unverified` until separately reconciled.

## Required owner-approved commercialization workflow

1. Read the dashboard summary on the **authorized host**, without modifying the storage or triggering the existing mail dispatch.
2. Classify and deduplicate real requests in a secure owner-controlled environment; do not infer lead identity from the random filename or assume support email notifications were delivered.
3. For each legitimate request, verify customer contact and the proposed service, scope, capacity, actual price, legal conditions, and availability.
4. Prepare an individual quote; **do not send, promise, charge, subscribe or commit without the owner's explicit per-action approval**.
5. After an approved sale, confirm the actual received funds from independent payment/banking/chain evidence. Do not use sent invoice emails, HTTP 200, checkout display or local MTA queue status as proof.
6. Close the commercial cycle only after service delivery, receipt, follow-up and support obligations are recorded.

## Scope of isolated test evidence

`tests/test_mpw_lead_desk_cli_20261114.py` runs **40 isolated cases** in synthetic temporary directories, using PHP OpenSSL to produce matching AEAD envelopes. It checks decrypted counts, integrity failures, OS/permissions fail-closed behavior, redaction, malicious references, service allowlist, age buckets, idempotent read-only behavior, newest-first ordering, pseudonymous worklist caps and **501-file pagination**. The test code cannot contact the live website and does not open real customer files. All 40 passed in the local isolated run; complete production acceptance and real lead existence have not been established.

## Avoiding unnecessary locks and inflated percentages

This script requires **PHP 7.4+ syntax** and OpenSSL, but does not require PHP 8.1-only `never` types; this was deliberately changed after validation. Mandatory authorization/security boundaries remain. **100% of 40 isolated test cases** is not **100% of the website, unified bot or revenue goal**.

Security note: the fixture-only override requires the explicit `MPW_INQUIRY_TEST_MODE=1` plus a private marker in a directory under the OS temporary root; this must never be used for real customer records. Do not execute test commands on production records. The script contains no API keys, customer emails or decryptable production data.

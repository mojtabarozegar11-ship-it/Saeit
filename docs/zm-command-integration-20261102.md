# Zomorod Melal — owner command-center integration (2026-11-02)

## Production scope

- Company management: `https://zomorodmelal.ir/business/`
- Private PHP application and SQLite stores: `/home/zomorod2/.private/zomorod-business/`
- Scope: the Zomorod Melal business only. No MojPlayWin changes.
- A manual command-center scan and the server-side six-hour schedule collect actionable findings from **accounting, inventory, organizational approvals, and the store**. They only create idempotent internal tasks and task events.
- **No** bank transfer, settlement confirmation, invoice posting, inventory mutation, contract signature, publication, external AI action, or real customer order is performed by the scanner.

## Deployed files

| Private server file | Function |
| --- | --- |
| `command_integrations.php` | Read-only SQLite bridges and idempotent owner tasks |
| `command_scan_cli.php` | CLI-only, locked, zero-approval scheduled scanner |
| `command_center.php` | Existing live center; minimally patched to import bridge, call it from `zmCcScan`, and label the scan button |

The private live `command_center.php` is not identical to any general repository `app.php` snapshot. Do not replace live `app.php` from the older repository copy. The two new source files on this feature branch can be reviewed independently.

## Exact integration hook on the live server

After the existing `command_quality.php` and `command_planner.php` imports:

```php
require_once __DIR__.'/command_integrations.php';
```

At the end of the existing `zmCcScan` function, replacing its prior return:

```php
$bridge=zmCcScanBridges($control,$uid);
return ['created'=>$created+$bridge['created'],
        'inspected'=>count($due)+count($stock)+$bridge['inspected']];
```

The UI scan button now refers to invoices, inventory, organizational desk and store.

## Scheduled execution

The cPanel account cron was extended by **one** line (31 lines before, 32 after):

```cron
17 */6 * * * /usr/local/bin/php /home/zomorod2/.private/zomorod-business/command_scan_cli.php >> /home/zomorod2/.private/zomorod-business/.command-scan-cron.log 2>&1 # ZM_CMD_SCAN_20261102
```

The server uses UTC+03:30. Each scan records `actor_id=0` for system-origin tasks; it does not impersonate the CEO. A private lock prevents overlapping runs. The CLI's accounting connection is explicitly `query_only=ON`.

## Evidence and remaining operational blockers

- Production PHP lint clean for all three involved PHP files; private PHP files mode `0600`.
- Live `/business/` HTTP 200; anonymous `/business/banking.php` HTTP 403.
- Bridge dry-run against live read-only stores: first scan created 2 mock tasks, second 0 (idempotence).
- Real control queue: first bridge scan created exactly 2 internal tasks; second 0. Sources: `store:payment_gateway` and `store:factory_drafts`.
- Current private store had **174 factory drafts**, **0 enabled catalogue products** and payment state **`not_configured`** at verification time. The company management ledger had **0 invoices** and **0 inventory items**. These are observations, not invented commercial results.
- The CLI executed twice successfully with zero duplicated work; the cron was installed and verified, but its first scheduled execution must be observed later.
- Real merchant acquiring, signed payment callbacks, product rights/delivery, source-code reconciliation, and real orders/settlements require their own independently verified evidence before marking the company fully operational.

## Recovery

Production backup directory: `/home/zomorod2/.backups/zm-command-bridge-20261102/`.

- `command_center.before.php`: exact pre-hook private module snapshot, SHA-256 `43bb5e250ba80e760f002badf5ca34f17bbb5c915164468ffc0226a301878357`.
- `crontab.before`: pre-install crontab snapshot, mode 600; contains potentially sensitive scheduled commands—never publish it.

Rollback should be **selective**: remove only the uniquely marked `ZM_CMD_SCAN_20261102` cron entry, restore the backed-up command-center file if verification fails, and retain the audit tasks as historical internal work rather than deleting records. Do not replace the entire crontab if unrelated jobs have changed since the backup.

## Subsequent same-day release — customer inquiry CRM and store acquisition

The command-center bridge was extended to inspect `master_customer_inbox.sqlite3` **read-only** and create at most one task per real Zomorod inquiry ticket. It copies **no customer name, email or message body** into the task queue. Tenant scoping is exact (`tenant='zomorod'`), and claimed order references never count as verified sales.

- New route: `/business/customer_inbox.php` — an authenticated, `admin`/`manager`-only private customer inbox. Reads the customer DB and management RBAC database with SQLite read-only connections and escapes all user-supplied fields.
- The live private `app.php` navigation contains an exact, conditional `store_manager`-adjacent link to the customer inbox. The older GitHub app snapshot was **not deployed** over the live module.
- The existing public `/store/` now offers an explicit enquiry CTA pointing to the existing authenticated-by-CSRF customer ingress `/ask-master/index.php`; it does **not** create an order or accept money.
- The existing free wheat seed-rate calculator file had SHA-256 `32858e6be6eb909bd1607df4242750276ffcdf4ee8fa431b6954c7ecbeb9e331`, matching its recorded digest. It remains a free educational product, not a paid transaction.
- At inspection the private store had **174 factory drafts**, including **125 `synth_` identifiers** and 49 non-`synth_` identifiers. All 174 were awaiting commercial approval. The customer inbox held **zero real questions** and the paid catalogue **zero products**. No false orders or leads were inserted.
- The updated bridge passed a temporary isolated SQLite test: one Zomorod-only test inquiry yielded one control-plane task, re-scan yielded zero duplicates, one other-tenant inquiry was excluded, and attempts to mutate the inquiry SQLite database through the bridge were rejected. The temporary test DB was removed.

Live acceptance checks: PHP lint clean for `app.php`, `command_integrations.php`, `customer_inbox.php`, and store `index.php`; store HTTP 200, customer ingress HTTP 200, anonymous inbox HTTP 403; inquiry callout appears exactly once on the public store page. The scheduled CLI still ran successfully twice after the bridge change, with no duplicate tasks.

Exact second-release backups: `/home/zomorod2/.backups/zm-sales-crm-20261102/`:

- `app.before.php` SHA-256 `2585a06ce7bbbd9b7aff4bac5fdd79a1ee7b2c45c8c13a8ad3aa647428e5652c`.
- `command_integrations.before.php` SHA-256 `258d3cae64a60a217913d4b0a05acbea7d3012ee9859e5e81bce66c42c1ce949`.
- `store.before.php` SHA-256 `0a57f8e974a67f54a973e6da7d5cb80202bf25a02d1171383f06ea94024267c6`.

Rollback only the CRM-specific additions if needed. The customer-inbox public route can be disabled without touching the bank or existing accounting modules. Keep existing legitimate messages and accounting records intact.

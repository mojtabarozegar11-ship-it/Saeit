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

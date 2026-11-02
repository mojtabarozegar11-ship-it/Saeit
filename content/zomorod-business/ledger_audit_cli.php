<?php
declare(strict_types=1);
/**
 * Owner-only cPanel CLI accounting integrity inspection.
 * Install at ~/.private/zomorod-business/tools/ledger_audit_cli.php (0600).
 * Output consists only of invariant booleans, not account, customer or ledger data.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
if (PHP_SAPI !== 'cli' || count($argv) !== 1) {
    http_response_code(403);
    exit(64);
}

$checks = [
    'private_database' => false,
    'schema_complete' => false,
    'sqlite_integrity' => false,
    'foreign_keys' => false,
    'balanced_journals_per_currency' => false,
    'no_invoice_overpayments' => false,
    'valid_invoice_currency' => false,
    'invoice_dates_present' => false,
    'active_administrator' => false,
];
$error = 'none';
try {
    $private = dirname(__DIR__);
    $path = $private.'/management.sqlite3';
    if (!extension_loaded('pdo_sqlite') || !is_dir($private) || is_link($private)
        || is_link($path) || !is_file($path) || !is_readable($path)
        || filesize($path) < 4096 || (fileperms($path) & 0777) !== 0600) {
        throw new RuntimeException('missing_or_unprotected_database');
    }
    $checks['private_database'] = true;
    $db = new PDO('sqlite:file:'.$path.'?mode=ro', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 12,
    ]);
    $db->exec('PRAGMA query_only=ON');
    $required = ['users','ledger_accounts','journal_entries','journal_lines','parties',
        'invoices','invoice_payments','inventory','inventory_movements','employees',
        'documents','projects','audit_events'];
    $tables = $db->query("SELECT name FROM sqlite_master WHERE type='table'")->fetchAll(PDO::FETCH_COLUMN);
    $checks['schema_complete'] = !array_diff($required, $tables);
    if (!$checks['schema_complete']) throw new RuntimeException('schema_incomplete');
    $checks['sqlite_integrity'] = $db->query('PRAGMA integrity_check')->fetchColumn() === 'ok';
    $checks['foreign_keys'] = $db->query('PRAGMA foreign_key_check')->fetch() === false;
    $imbalanced = $db->query("SELECT COUNT(*) FROM (
      SELECT j.id, l.currency, COUNT(l.id) lines,
        COALESCE(SUM(l.debit),0) debits, COALESCE(SUM(l.credit),0) credits
      FROM journal_entries j LEFT JOIN journal_lines l ON l.entry_id=j.id
      GROUP BY j.id,l.currency
      HAVING COUNT(l.id)<2 OR COALESCE(SUM(l.debit),0)!=COALESCE(SUM(l.credit),0)
    )")->fetchColumn();
    $checks['balanced_journals_per_currency'] = (int)$imbalanced === 0;
    $overpaid = $db->query("SELECT COUNT(*) FROM (
      SELECT i.id FROM invoices i LEFT JOIN invoice_payments p ON p.invoice_id=i.id
      GROUP BY i.id HAVING COALESCE(SUM(p.amount),0)>i.amount
    )")->fetchColumn();
    $checks['no_invoice_overpayments'] = (int)$overpaid === 0;
    $invalidCurrency = $db->query("SELECT COUNT(*) FROM invoices
      WHERE currency NOT IN ('IRR','USD','EUR','AED') OR currency IS NULL")->fetchColumn();
    $checks['valid_invoice_currency'] = (int)$invalidCurrency === 0;
    $invalidDates = $db->query("SELECT COUNT(*) FROM invoices WHERE
      invoice_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
      OR due_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")->fetchColumn();
    $checks['invoice_dates_present'] = (int)$invalidDates === 0;
    $administrators = $db->query("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1")->fetchColumn();
    $checks['active_administrator'] = (int)$administrators > 0;
    $db = null;
} catch (Throwable $exception) {
    // Never print private paths, SQL or database error messages to remote logs.
    $error = $checks['private_database'] ? 'accounting_invariant_query_failed' : 'database_access_failed';
}
$passed = !in_array(false, $checks, true) && $error === 'none';
echo json_encode([
    'system' => 'zomorodmelal-accounting',
    'result' => $passed ? 'PASS' : 'REVIEW_REQUIRED',
    'checked_at_utc' => gmdate('Y-m-d\TH:i:s\Z'),
    'checks' => $checks,
    'read_only' => true,
    'external_bank_reconciliation' => 'NOT_PROVEN',
    'offsite_restore' => 'NOT_PROVEN',
    'error_category' => $error,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)."\n";
exit($passed ? 0 : 2);

<?php
declare(strict_types=1);
/**
 * Private, cron-safe company task scanner. Run using PHP CLI only.
 * Reads accounting/workflow/store; only writes idempotent command-center tasks.
 * actor_id=0 explicitly identifies a system-created task, not a human approval.
 */
if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit(1);
}
ini_set('display_errors', 'stderr');
umask(0077);

function bail(string $message, int $status=422): never {
    throw new RuntimeException($message, $status);
}
function mbSafeLen(string $value): int {
    return function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
}
function money(int $cents): string {
    return number_format($cents/100, 2, '.', ',');
}
function q(PDO $db, string $sql, array $args=[]): array {
    $statement = $db->prepare($sql);
    $statement->execute($args);
    return $statement->fetchAll(PDO::FETCH_ASSOC);
}

try {
    $private = __DIR__;
    $ledger = $private.'/management.sqlite3';
    $lockPath = $private.'/.command-scan.lock';
    if (!is_file($ledger) || is_link($ledger) || is_link($lockPath)) {
        throw new RuntimeException('Accounting file missing or unsafe');
    }
    $lock = fopen($lockPath, 'c');
    if (!$lock || !chmod($lockPath, 0600) || !flock($lock, LOCK_EX | LOCK_NB)) {
        throw new RuntimeException('Another scanner is running or lock unavailable');
    }
    $company = new PDO('sqlite:'.$ledger, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 12,
    ]);
    $company->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=12000;');
    require_once $private.'/command_center.php';
    $control = zmCcDb($private);
    $result = zmCcScan($company, $control, 0);
    echo json_encode([
        'status'=>'ok',
        'timestamp_utc'=>gmdate('Y-m-d\TH:i:s\Z'),
        'inspected'=>$result['inspected'],
        'new_tasks'=>$result['created'],
        'scope'=>'internal_tasks_only',
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), PHP_EOL;
    flock($lock, LOCK_UN);
    fclose($lock);
} catch (Throwable $error) {
    // No customer, invoice, payment, or credential details are sent to cron mail.
    fwrite(STDERR, 'Company scan failed: '.get_class($error).PHP_EOL);
    exit(1);
}

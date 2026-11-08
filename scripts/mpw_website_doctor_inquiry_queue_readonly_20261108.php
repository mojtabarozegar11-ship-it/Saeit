<?php
declare(strict_types=1);
/*
 * Website Doctor: private, read-only intake queue for an authorized cPanel CLI.
 * Never sends mail, creates quotes, accepts payments, changes records or prints PII.
 *
 * Usage: php mpw_website_doctor_inquiry_queue_readonly_20261108.php summary
 *        php mpw_website_doctor_inquiry_queue_readonly_20261108.php references
 */
if (PHP_SAPI !== 'cli' || !in_array(($argv[1] ?? ''), ['summary', 'references'], true) || count($argv) !== 2) {
    fwrite(STDERR, "CLI-only: summary | references\n");
    exit(2);
}
umask(0077);
header_remove();
$root = '/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries';
function abort_safely(string $reason): void {
    fwrite(STDERR, "MPW_PRIVATE_QUEUE_UNAVAILABLE:" . $reason . "\n");
    exit(2);
}
if (!extension_loaded('openssl') || !is_dir($root) || is_link($root)) abort_safely('PRIVATE_STORE');
if (function_exists('posix_geteuid') && @fileowner($root) !== posix_geteuid()) abort_safely('OWNER_MISMATCH');
$keyFile = $root . '/.inquiry-key';
if (!is_file($keyFile) || is_link($keyFile)) abort_safely('KEY_MISSING');
$key = @file_get_contents($keyFile);
if ($key === false || strlen($key) !== 32) abort_safely('KEY_INVALID');
$files = @scandir($root);
if (!is_array($files)) abort_safely('SCAN_FAILURE');
$files = array_values(array_filter($files, static function ($name): bool {
    return (bool) preg_match('/^[0-9]{8}-[A-F0-9]{18}\.json$/D', $name);
}));
rsort($files, SORT_STRING);
$cap = 250;
$out = [
    'status' => 'private_readonly',
    'service' => 'website-doctor',
    'scanned_records' => 0,
    'qualified_records' => 0,
    'last_7_days' => 0,
    'invalid_records' => 0,
    'truncated' => count($files) > $cap,
];
$references = [];
$sevenDaysAgo = time() - 7 * 86400;
foreach (array_slice($files, 0, $cap) as $file) {
    $out['scanned_records']++;
    $path = $root . '/' . $file;
    if (!is_file($path) || is_link($path) || @filesize($path) > 12000) {
        $out['invalid_records']++;
        continue;
    }
    $json = @file_get_contents($path);
    $obj = $json === false ? null : json_decode($json, true);
    if (!is_array($obj) || ($obj['v'] ?? null) !== 1) {
        $out['invalid_records']++;
        continue;
    }
    $values = [];
    foreach (['iv', 'tag', 'cipher'] as $field) {
        if (!isset($obj[$field]) || !is_string($obj[$field])) continue 2;
        $values[$field] = base64_decode($obj[$field], true);
        if ($values[$field] === false) continue 2;
    }
    if (strlen($values['iv']) !== 12 || strlen($values['tag']) !== 16) {
        $out['invalid_records']++;
        continue;
    }
    $plain = @openssl_decrypt(
        $values['cipher'], 'aes-256-gcm', $key,
        OPENSSL_RAW_DATA, $values['iv'], $values['tag']
    );
    $lead = is_string($plain) ? json_decode($plain, true) : null;
    if (!is_array($lead) || ($lead['source'] ?? '') !== 'first_party_mpw_revenue' ||
        ($lead['consent'] ?? null) !== true) {
        $out['invalid_records']++;
        continue;
    }
    if (($lead['service'] ?? '') !== 'website-doctor') continue;
    $out['qualified_records']++;
    $when = strtotime((string) ($lead['created_at'] ?? ''));
    if ($when !== false && $when >= $sevenDaysAgo && $when <= time() + 300) $out['last_7_days']++;
    if ($argv[1] === 'references') {
        // Only a random private reference and UTC timestamp; no name, email or project details.
        $references[] = [
            'reference' => substr($file, 9, 18),
            'received_utc' => ($when === false) ? null : gmdate('c', $when),
        ];
    }
}
if ($argv[1] === 'references') $out['references'] = $references;
echo 'MPW_WEBSITE_DOCTOR_QUEUE=' . json_encode($out, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";

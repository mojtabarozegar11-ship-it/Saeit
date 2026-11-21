<?php
/**
 * MojPlayWin first-party, optional funnel event collector.
 * No cookies, credentials, IP addresses, email, wallet, invoice ID or URL query
 * strings are persisted. Private output is outside the document root.
 */
declare(strict_types=1);
header('Cache-Control: no-store, max-age=0');
header('Content-Security-Policy: default-src \'none\'; frame-ancestors \'none\'');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Access-Control-Allow-Origin: none');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    exit;
}
$host = strtolower(explode(':', (string) ($_SERVER['HTTP_HOST'] ?? ''))[0]);
$origin = (string) ($_SERVER['HTTP_ORIGIN'] ?? '');
if (!in_array($host, ['mojplaywin.com', 'www.mojplaywin.com'], true)
    || $origin !== 'https://' . $host
    || !in_array((string) ($_SERVER['HTTP_SEC_FETCH_SITE'] ?? 'same-origin'), ['same-origin', 'none'], true)
    || (int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 1200
    || stripos((string) ($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json') !== 0
) {
    http_response_code(403);
    exit;
}
$input = file_get_contents('php://input', false, null, 0, 1201);
if ($input === false || strlen($input) > 1200) {
    http_response_code(400);
    exit;
}
try {
    $x = json_decode($input, true, 16, JSON_THROW_ON_ERROR);
} catch (JsonException $exception) {
    http_response_code(400);
    exit;
}
if (!is_array($x)) {
    http_response_code(400);
    exit;
}
$events = ['page', 'engaged', 'product_click', 'plan_click', 'buy_click', 'form_submit', 'help_click'];
$pages = [
    '/store/' => 'store',
    '/store/product/' => 'store',
    '/commerce/trx-easy/' => 'store',
    '/commerce/book/' => 'store',
    '/commerce/trx-easy/invoice/' => 'store',
    '/commerce/trx-easy/purchases/' => 'store',
    '/commerce/trx-easy/recover/' => 'store',
    '/moj-prop/' => 'prop',
    '/moj-prop/starter-30-trx/' => 'prop',
    '/moj-prop/payment/' => 'prop',
    '/moj-prop/catalog/' => 'prop',
    '/moj-prop/rules/' => 'prop',
    '/moj-prop/contact/' => 'prop',
    '/moj-prop/signals/' => 'prop',
    '/mojprop-starter30-checkout/' => 'prop',
];
$event = $x['event'] ?? null;
$page = $x['page'] ?? null;
$session = $x['session'] ?? null;
if (!is_string($event) || !in_array($event, $events, true)
    || !is_string($page) || !array_key_exists($page, $pages)
    || !is_string($session) || preg_match('/\A[a-f0-9]{32}\z/D', $session) !== 1
) {
    http_response_code(400);
    exit;
}
/* UTM values are deliberately restricted to short campaign labels. */
$utm = [];
foreach (['source' => 32, 'medium' => 32, 'campaign' => 48] as $key => $limit) {
    $value = $x[$key] ?? '';
    if (!is_string($value) || strlen($value) > $limit
        || ($value !== '' && preg_match('/\A[a-zA-Z0-9_-]+\z/D', $value) !== 1)) {
        $value = '';
    }
    $utm[$key] = $value;
}
$record = [
    'ts' => gmdate('Y-m-d\TH:i:s\Z'),
    'site' => $pages[$page],
    'event' => $event,
    'page' => $page,
    'session' => $session,
    'source' => $utm['source'],
    'medium' => $utm['medium'],
    'campaign' => $utm['campaign'],
];
$root = '/home/zomorod2/.mpw-measure/events';
if (!is_dir($root) || is_link($root)) {
    http_response_code(503);
    exit;
}
$path = $root . '/' . gmdate('Y-m-d') . '.jsonl';
umask(0077);
$fh = @fopen($path, 'ab');
if ($fh === false) {
    http_response_code(503);
    exit;
}
$ok = false;
if (flock($fh, LOCK_EX)) {
    $st = fstat($fh);
    $line = json_encode($record, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
    if ($st !== false && (int) $st['size'] + strlen($line) <= 8 * 1024 * 1024) {
        $ok = fwrite($fh, $line) === strlen($line);
        fflush($fh);
    }
    flock($fh, LOCK_UN);
}
fclose($fh);
http_response_code($ok ? 204 : 503);

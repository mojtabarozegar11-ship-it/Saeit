<?php
declare(strict_types=1);
/**
 * Moj Play Win: narrowly scoped canonical HTML filter for three additional PUBLIC GET pages.
 * This is NOT a generic reverse proxy: origin host and allowed routes are fixed.
 * The original Django app, Passenger, and all protected sites remain unchanged.
 * nginx/apache/LiteSpeed rewrite must exempt __mpw_canon_passthru=1.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
$allowed = [
    'market' => '/market/',
    'industry' => '/industry/',
    'economy' => '/economy/',
];
$slug = $_GET['__mpw_canon_route'] ?? null;
if (!is_string($slug) || !isset($allowed[$slug])
    || !in_array(strtolower((string)($_SERVER['HTTP_HOST'] ?? '')), ['mojplaywin.com','www.mojplaywin.com'], true)) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    exit('Not found');
}
$path = $allowed[$slug];
$method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? ''));
if ($method !== 'GET') {
    http_response_code(405);
    header('Allow: GET');
    exit;
}
$forward = $_GET;
unset($forward['__mpw_canon_route'], $forward['__mpw_canon_passthru'], $forward['__mpw_probe']);
foreach (array_keys($forward) as $key) {
    if (!is_string($key) || strlen($key) > 90 || preg_match('/[^a-zA-Z0-9_\.\[\]-]/', $key)) {
        unset($forward[$key]);
    }
}
$passthru = ['__mpw_canon_passthru' => '1'];
$query = http_build_query($forward + $passthru, '', '&', PHP_QUERY_RFC3986);
$origin = 'https://mojplaywin.com' . $path . '?' . $query;
header('X-Content-Type-Options: nosniff');
header('Cache-Control: private, no-store, max-age=0');
header('Vary: Cookie');
function fallbackToOriginal(string $path, string $query): never {
    header('Location: ' . $path . '?' . $query, true, 307);
    exit;
}
$curl = curl_init($origin);
if ($curl === false) fallbackToOriginal($path, $query);
$headers = ['Accept: text/html', 'Accept-Encoding: identity', 'Cache-Control: no-cache'];
$cookie = $_SERVER['HTTP_COOKIE'] ?? '';
if (is_string($cookie) && $cookie !== '' && strlen($cookie) <= 8192 && !preg_match('/[\r\n]/', $cookie)) {
    // The request is forwarded ONLY to the same HTTPS domain; no third parties.
    $headers[] = 'Cookie: ' . $cookie;
}
$acceptLanguage = $_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '';
if (is_string($acceptLanguage) && $acceptLanguage !== ''
    && strlen($acceptLanguage) < 250 && !preg_match('/[\r\n]/', $acceptLanguage)) {
    $headers[] = 'Accept-Language: ' . $acceptLanguage;
}
curl_setopt_array($curl, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADER => true,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_CONNECTTIMEOUT => 4,
    CURLOPT_TIMEOUT => 12,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
    CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
    CURLOPT_ENCODING => 'identity',
    CURLOPT_USERAGENT => 'MojPlayWin-canonical-scoped-same-domain/1.0',
    CURLOPT_HTTPHEADER => $headers,
]);
$response = curl_exec($curl);
$status = curl_getinfo($curl, CURLINFO_HTTP_CODE);
$mime = curl_getinfo($curl, CURLINFO_CONTENT_TYPE);
$headerSize = curl_getinfo($curl, CURLINFO_HEADER_SIZE);
$error = curl_errno($curl);
curl_close($curl);
if (!is_string($response) || $error !== 0 || $status !== 200 || !is_int($headerSize)
    || $headerSize <= 0 || !is_string($mime) || stripos($mime, 'text/html') !== 0) {
    fallbackToOriginal($path, $query);
}
$originalHeaders = substr($response, 0, $headerSize);
$body = substr($response, $headerSize);
$old = '<link rel="canonical" href="https://zomorodmelal.ir' . $path . '">';
$new = '<link rel="canonical" href="https://mojplaywin.com' . $path . '">';
if (strlen($body) < 1000 || strlen($body) > 700000
    || substr_count($body, $old) !== 1
    || substr_count($body, 'rel="canonical"') !== 1) {
    fallbackToOriginal($path, $query);
}
// Forward only explicitly allowed security headers / cookie refreshes.
foreach (preg_split('/\r?\n/', $originalHeaders) as $line) {
    if (!is_string($line) || strpos($line, ':') === false || strpbrk($line, "\r\n") !== false) continue;
    [$key] = explode(':', $line, 2);
    $name = strtolower(trim($key));
    if (in_array($name, ['set-cookie', 'content-security-policy',
        'x-frame-options', 'referrer-policy', 'permissions-policy',
        'strict-transport-security'], true)) {
        header($line, $name !== 'set-cookie');
    }
}
$body = str_replace($old, $new, $body);
header('Content-Type: text/html; charset=utf-8');
header('X-MPW-Canonical-Edge: main-only');
echo $body;

<?php
declare(strict_types=1);
/**
 * TEMPORARY, PUBLIC-READ-ONLY CANARY for a surgical canonical fix on
 * Moj Play Win's six informational pages. It neither changes the Django
 * process nor performs writes to user databases or to any child site.
 *
 * An internal CGI rewrite for production has NOT yet been authorized.
 * This canary is gated to one known probe token and removed after QA.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '0');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');
$probeKey = isset($_GET['__mpw_probe']) && is_string($_GET['__mpw_probe'])
    ? $_GET['__mpw_probe'] : '';
if ($probeKey !== 'mpw-canonical-bridge-20261017-verification') {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    exit('Not found');
}
$allowed = [
    'store' => '/store/',
    'research' => '/research/',
    'company' => '/company/',
    'knowledge' => '/knowledge/',
    'agriculture' => '/ventures/agriculture/',
    'jewelry' => '/ventures/jewelry-gold/',
];
$slug = isset($_GET['__mpw_canon_route']) && is_string($_GET['__mpw_canon_route'])
    ? $_GET['__mpw_canon_route'] : '';
if (!isset($allowed[$slug])) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    exit('Not found');
}
$path = $allowed[$slug];
// A future production rewrite must exempt this marker to prevent loops.
$upstreamUrl = 'https://mojplaywin.com' . $path . '?__mpw_canon_passthru=1';
$curl = curl_init($upstreamUrl);
if ($curl === false) {
    http_response_code(503);
    exit;
}
curl_setopt_array($curl, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADER => true,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_CONNECTTIMEOUT => 4,
    CURLOPT_TIMEOUT => 11,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
    CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
    CURLOPT_USERAGENT => 'MojPlayWin-main-only-canonical-safe-probe/1.0',
    CURLOPT_HTTPHEADER => ['Accept: text/html', 'Accept-Encoding: identity', 'Cache-Control: no-cache'],
    CURLOPT_ENCODING => 'identity',
]);
$response = curl_exec($curl);
$status = curl_getinfo($curl, CURLINFO_HTTP_CODE);
$mime = curl_getinfo($curl, CURLINFO_CONTENT_TYPE);
$headerSize = curl_getinfo($curl, CURLINFO_HEADER_SIZE);
$error = curl_errno($curl);
curl_close($curl);
if (!is_string($response) || $error !== 0 || $status !== 200
    || !is_string($mime) || stripos($mime, 'text/html') !== 0
    || !is_int($headerSize) || $headerSize < 1) {
    http_response_code(503);
    header('X-MPW-Canary-Stage: upstream');
    header('X-MPW-Canary-Curl-Error: ' . (int)$error);
    header('X-MPW-Canary-Upstream-Status: ' . (int)$status);
    header('X-MPW-Canary-Mime-OK: ' . (int)(is_string($mime) && stripos($mime, 'text/html') === 0));
    header('X-MPW-Canary-Header-Bytes: ' . (int)$headerSize);
    header('Content-Type: text/plain; charset=utf-8');
    exit('Source temporarily unavailable');
}
$body = substr($response, $headerSize);
$old = '<link rel="canonical" href="https://zomorodmelal.ir' . $path . '">';
$new = '<link rel="canonical" href="https://mojplaywin.com' . $path . '">';
if (substr_count($body, $old) !== 1 || substr_count($body, 'rel="canonical"') !== 1
    || strlen($body) > 700000 || strlen($body) < 1000) {
    http_response_code(503);
    header('X-MPW-Canary-Stage: canonical');
    header('X-MPW-Canary-Wrong-Tag-Count: ' . substr_count($body, $old));
    header('X-MPW-Canary-Canonical-Count: ' . substr_count($body, 'rel="canonical"'));
    header('X-MPW-Canary-Body-Bytes: ' . strlen($body));
    header('Content-Type: text/plain; charset=utf-8');
    exit('Source validation failed');
}
$body = str_replace($old, $new, $body);
header('Content-Type: text/html; charset=utf-8');
header('X-MPW-Canary: canonical-only');
header('Vary: Cookie');
header('Content-Length: ' . strlen($body));
echo $body;

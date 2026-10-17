<?php
declare(strict_types=1);
/**
 * Moj Play Win public sitemap live augmentation, isolated from shared Django.
 * It fetches the existing MojPlayWin sitemap via a strictly same-origin HTTPS
 * bypass, then adds only market, industry and economy URLs when absent.
 * The original dynamic sitemap entries remain byte-for-byte unchanged.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
$host = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
if (!in_array($host, ['mojplaywin.com', 'www.mojplaywin.com'], true)
    || strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? '')) !== 'GET') {
    http_response_code(404);
    exit('Not found');
}
header('X-Content-Type-Options: nosniff');
header('Cache-Control: public, max-age=300');
function fallbackSitemap(): never {
    header('Location: /sitemap.xml?__mpw_sitemap_passthru=1', true, 307);
    exit;
}
$curl = curl_init('https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1');
if ($curl === false) fallbackSitemap();
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
    CURLOPT_HTTPHEADER => ['Accept: application/xml,text/xml,*/*', 'Cache-Control: no-cache', 'Accept-Encoding: identity'],
    CURLOPT_USERAGENT => 'MojPlayWin-main-only-dynamic-sitemap/1.0',
]);
$result = curl_exec($curl);
$code = (int)curl_getinfo($curl, CURLINFO_HTTP_CODE);
$type = (string)curl_getinfo($curl, CURLINFO_CONTENT_TYPE);
$headSize = curl_getinfo($curl, CURLINFO_HEADER_SIZE);
$err = curl_errno($curl);
curl_close($curl);
if (!is_string($result) || $code !== 200 || $err !== 0
    || !is_int($headSize) || $headSize < 1
    || (stripos($type, 'xml') === false)) fallbackSitemap();
$original = substr($result, $headSize);
if (strlen($original) < 1000 || strlen($original) > 950000
    || substr_count($original, '</urlset>') !== 1
    || substr_count($original, '<urlset') !== 1
    || substr_count($original, '<loc>') < 20
    || substr_count($original, '<loc>') > 3000
    || strpos($original, 'https://mojplaywin.com/') === false
    || strpos($original, 'https://zomorodmelal.ir/') !== false) fallbackSitemap();
$paths = ['/market/', '/industry/', '/economy/'];
$extra = '';
foreach ($paths as $path) {
    $url = 'https://mojplaywin.com' . $path;
    // The original XML uses URLs under a single trusted domain.
    $loc = '<loc>' . $url . '</loc>';
    if (substr_count($original, $loc) > 1) fallbackSitemap();
    if (substr_count($original, $loc) === 0) {
        $extra .= '<url>' . $loc . '</url>';
    }
}
$closing = strrpos($original, '</urlset>');
if ($closing === false) fallbackSitemap();
$body = substr($original, 0, $closing) . $extra . substr($original, $closing);
header('Content-Type: application/xml; charset=utf-8');
header('X-MPW-Sitemap-Augmentation: three-indexable-main-pages');
echo $body;

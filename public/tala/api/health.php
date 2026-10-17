<?php
// Public capability probe for the isolated Tala subsite. Never expose configuration values.
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$drivers = class_exists('PDO') ? PDO::getAvailableDrivers() : [];
$home = getenv('HOME') ?: '';
$homeWritable = $home !== '' && is_dir($home) && is_writable($home);
$privateStore = $home !== '' ? $home . '/.tala-private' : '';
$privateStoreWritable = $privateStore !== '' && is_dir($privateStore) && is_writable($privateStore);
$privateProbe = $privateStoreWritable ? @tempnam($privateStore, '.probe-') : false;
if ($privateProbe !== false) {
    $privateStoreWritable = @file_put_contents($privateProbe, 'ok', LOCK_EX) === 2;
    @unlink($privateProbe);
}
$probe = @tempnam(__DIR__, '.tala-probe-');
$apiWritable = false;
if ($probe !== false) {
    $apiWritable = @file_put_contents($probe, 'ok', LOCK_EX) === 2;
    @unlink($probe);
}

http_response_code(200);
echo json_encode([
    'scope' => 'tala',
    'runtime' => 'php',
    'pdo_sqlite' => in_array('sqlite', $drivers, true),
    'private_home_writable' => $homeWritable,
    'api_storage_writable' => $apiWritable,
    'private_store_writable' => $privateStoreWritable,
], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

<?php
declare(strict_types=1);
$root = dirname(__DIR__, 2);
$entry = $root . '/.private/zomorod-business/app.php';
if (!is_file($entry)) {
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store');
    echo 'Management module is undergoing maintenance.';
    exit;
}
require $entry;
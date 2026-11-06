<?php
declare(strict_types=1);
// Public entry point; private logic and data remain outside public_html.
$root = dirname(__DIR__, 2);
$entry = $root . '/.private/zomorod-business/service_inquiries.php';
if (!is_file($entry) || is_link($entry)) {
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store');
    echo 'Service inquiry desk is unavailable.';
    exit;
}
require $entry;

<?php
declare(strict_types=1);
/**
 * One-time private approvals CSV receiver. CLI only; no web route.
 * The envelope is RSA OAEP wrapped AES-256-GCM ciphertext of GZIP CSV bytes.
 */
ini_set('display_errors', '0');
ini_set('log_errors', '1');
function zmReceiveFail(string $reason): never {
    fwrite(STDERR, "APPROVAL_SEALED_RECEIVE=BLOCKED_".$reason."\n");
    exit(3);
}
if (PHP_SAPI !== 'cli' || $argc !== 3) zmReceiveFail('CLI_ONLY');
if (!extension_loaded('openssl') || !function_exists('gzdecode')) zmReceiveFail('CRYPTO_UNAVAILABLE');

$private = '/home/zomorod2/.private/zomorod-business';
$destination = $private.'/zomorod_projects_import_20261031.csv';
$recipient = $private.'/.chat-command-rsa.key';
$envelopePath = (string)$argv[1];
$expectedPath = (string)$argv[2];
$sourceSha = '40c09b1aff17143cf315884177b61a35c6b1d62aa30a445056cfd8303deb3366';
$sourceSize = 52072;
$purpose = 'zomorod-approval-csv-import-20261031-v1';
if ($expectedPath !== $destination) zmReceiveFail('DESTINATION_SCOPE');
if (!is_dir($private) || is_link($private)) zmReceiveFail('PRIVATE_DIR_MISSING');
$dirInfo = @stat($private);
if ($dirInfo === false || $dirInfo['uid'] !== getmyuid() || ($dirInfo['mode'] & 0077) !== 0) {
    zmReceiveFail('PRIVATE_DIR_PERMISSIONS');
}
if (file_exists($destination) || is_link($destination)) zmReceiveFail('DESTINATION_EXISTS');
if (!is_file($recipient) || is_link($recipient)) zmReceiveFail('PRIVATE_KEY_MISSING');
if (!is_file($envelopePath) || is_link($envelopePath)) zmReceiveFail('ENVELOPE_MISSING');
foreach ([$recipient, $envelopePath] as $file) {
    $info = @stat($file);
    if ($info === false || $info['uid'] !== getmyuid() || ($info['mode'] & 0077) !== 0) {
        zmReceiveFail('INPUT_PERMISSIONS');
    }
}
$encoded = @file_get_contents($envelopePath);
if ($encoded === false || strlen($encoded) > 22001 || strlen($encoded) < 600) {
    zmReceiveFail('ENVELOPE_SIZE');
}
try {
    $env = json_decode($encoded, true, 16, JSON_THROW_ON_ERROR);
    if (!is_array($env) || array_keys($env) !== ['alg', 'ct', 'ek', 'issued_at', 'iv', 'plain_size', 'purpose', 'sha256', 'tag', 'v']) {
        zmReceiveFail('ENVELOPE_STRUCTURE');
    }
    if ($env['v'] !== 1 || $env['purpose'] !== $purpose ||
        $env['alg'] !== 'RSA-OAEP-SHA1+AES-256-GCM+GZIP' ||
        $env['plain_size'] !== $sourceSize ||
        $env['sha256'] !== $sourceSha ||
        !is_int($env['issued_at']) || abs(time() - $env['issued_at']) > 3600) {
        zmReceiveFail('ENVELOPE_POLICY');
    }
    foreach (['ct', 'ek', 'iv', 'tag'] as $field) {
        if (!is_string($env[$field]) || !preg_match('/^[A-Za-z0-9+\/]+={0,2}$/D', $env[$field])) {
            zmReceiveFail('ENVELOPE_BASE64');
        }
    }
    $ek = base64_decode($env['ek'], true);
    $iv = base64_decode($env['iv'], true);
    $tag = base64_decode($env['tag'], true);
    $ct = base64_decode($env['ct'], true);
    if ($ek === false || $iv === false || $tag === false || $ct === false ||
        !in_array(strlen($ek), [384, 512], true) || strlen($iv) !== 12 ||
        strlen($tag) !== 16 || strlen($ct) > 20000) {
        zmReceiveFail('ENVELOPE_LENGTH');
    }
    $pem = @file_get_contents($recipient);
    $key = $pem === false ? false : openssl_pkey_get_private($pem);
    if ($key === false) zmReceiveFail('RECIPIENT_KEY');
    $aesKey = '';
    if (!openssl_private_decrypt($ek, $aesKey, $key, OPENSSL_PKCS1_OAEP_PADDING) ||
        strlen($aesKey) !== 32) {
        zmReceiveFail('KEY_UNWRAP');
    }
    $aad = $purpose.'|'.$sourceSize.'|'.$sourceSha.'|'.$env['issued_at'];
    $gz = openssl_decrypt($ct, 'aes-256-gcm', $aesKey, OPENSSL_RAW_DATA, $iv, $tag, $aad);
    if ($gz === false) zmReceiveFail('GCM_AUTHENTICATION');
    $csv = gzdecode($gz, 2000000);
    if (!is_string($csv) || strlen($csv) !== $sourceSize ||
        !hash_equals($sourceSha, hash('sha256', $csv))) {
        zmReceiveFail('SOURCE_INTEGRITY');
    }
    $temp = tempnam($private, '.approval-import-');
    if ($temp === false) zmReceiveFail('PRIVATE_TEMP');
    try {
        if (!chmod($temp, 0600) || file_put_contents($temp, $csv, LOCK_EX) !== $sourceSize) {
            zmReceiveFail('PRIVATE_WRITE');
        }
        if (!@link($temp, $destination)) zmReceiveFail('DESTINATION_COLLISION');
    } finally {
        @unlink($temp);
    }
    echo "APPROVAL_SEALED_RECEIVE=INSTALLED\n";
    echo "SOURCE_SHA256=".$sourceSha."\n";
    echo "SOURCE_BYTES=".$sourceSize."\n";
    echo "PLAINTEXT_LOGGED=no\n";
} catch (Throwable $e) {
    zmReceiveFail('VALIDATION_FAILURE');
}

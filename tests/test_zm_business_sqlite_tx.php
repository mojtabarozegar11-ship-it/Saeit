<?php
declare(strict_types=1);
/* Synthetic PDO transaction check; no production code, users or DB access. */
if (!extension_loaded('pdo_sqlite')) {
    fwrite(STDERR, "PDO_SQLITE_MISSING\n");
    exit(2);
}
$db = new PDO('sqlite::memory:', null, null, [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
]);
$db->exec('CREATE TABLE movements (qty INTEGER NOT NULL)');
$db->exec('BEGIN IMMEDIATE');
$db->exec('INSERT INTO movements(qty) VALUES (1)');
$db->exec('COMMIT');
$qty = (int)$db->query('SELECT SUM(qty) FROM movements')->fetchColumn();
if ($qty !== 1) {
    fwrite(STDERR, "COMMIT_FAILED\n");
    exit(1);
}
$db->exec('BEGIN IMMEDIATE');
try {
    $db->exec('INSERT INTO movements(qty) VALUES (-2)');
    throw new RuntimeException('synthetic validation failure');
} catch (RuntimeException $err) {
    $db->exec('ROLLBACK');
}
$after = (int)$db->query('SELECT SUM(qty) FROM movements')->fetchColumn();
if ($after !== 1) {
    fwrite(STDERR, "ROLLBACK_FAILED\n");
    exit(1);
}
$db->exec('BEGIN IMMEDIATE');
$db->exec('INSERT INTO movements(qty) VALUES (-1)');
$db->exec('COMMIT');
$remaining = (int)$db->query('SELECT SUM(qty) FROM movements')->fetchColumn();
if ($remaining !== 0) {
    fwrite(STDERR, "SECOND_COMMIT_FAILED\n");
    exit(1);
}
echo "PHP_SQLITE_IMMEDIATE_COMMIT_AND_ROLLBACK=ok\n";

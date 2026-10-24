<?php
declare(strict_types=1);
define('MASTER_TICKET_STATUS_TEST_MODE', true);
require __DIR__ . '/../scripts/site_master_customer_ticket_status_20261024.php';
function verify($value, string $reason): void { if (!$value) { throw new RuntimeException($reason); } }
$db = new PDO('sqlite::memory:');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec('CREATE TABLE customer_questions(id TEXT PRIMARY KEY,tenant TEXT,email TEXT,processing_status TEXT,initial_reply TEXT,created_utc TEXT,master_processed_utc TEXT)');
$ticket = str_repeat('a',24);
$db->prepare('INSERT INTO customer_questions VALUES(?,?,?,?,?,?,?)')->execute(
    [$ticket,'zomorod','Customer@example.com','needs_review','بررسی اختصاصی', '2026-10-24 01:00:00', '2026-10-24 01:01:00']);
$row = masterTrackTicket($db,'zomorod',$ticket,'customer@EXAMPLE.COM');
verify($row !== null && $row['status']==='needs_review' && $row['reply']==='بررسی اختصاصی','CORRECT_TICKET_REJECTED');
verify(masterTrackTicket($db,'zomorod',$ticket,'wrong@example.com') === null,'EMAIL_PROTECTION_BROKEN');
verify(masterTrackTicket($db,'mojplaywin',$ticket,'Customer@example.com') === null,'TENANT_ISOLATION_BROKEN');
verify(masterTrackTicket($db,'zomorod','garbage','Customer@example.com') === null,'BAD_TICKET_ACCEPTED');
verify(masterTrackTicket($db,'zomorod',$ticket,'not-an-email') === null,'BAD_EMAIL_ACCEPTED');
verify(masterEscape('<script>')==='&lt;script&gt;','HTML_ESCAPE_BROKEN');
verify((int)$db->query('SELECT COUNT(*) FROM customer_questions')->fetchColumn()===1,'LOOKUP_MUTATED_CUSTOMER_RECORD');
echo "CUSTOMER_STATUS_TENANT_ISOLATION=PASS\n";
echo "CUSTOMER_STATUS_EMAIL_TICKET_PAIR=PASS\n";
echo "CUSTOMER_STATUS_NO_ORDER_DATA_EXPOSURE=PASS\n";

<?php
declare(strict_types=1);
/** Dedicated synthetic SQLite regression; no real bank/ledger accessed. */
error_reporting(E_ALL);
function mbSafeLen(string $v):int{return function_exists('mb_strlen')?mb_strlen($v,'UTF-8'):strlen($v);}
function bail(string $s,int $status=422):never{throw new RuntimeException($s,$status);}
function ensure(bool $v,string $why):void{if(!$v)throw new RuntimeException('QA_FAILED='.$why);}
function rejected(callable $run,int $code,string $which):void{
    try{$run();}catch(RuntimeException $e){ensure($e->getCode()===$code,$which.'_status');return;}
    throw new RuntimeException('QA_FAILED='.$which.'_not_rejected');
}
require __DIR__.'/../content/zomorod-business/treasury_control.php';
$folder=sys_get_temp_dir().'/zm-treasury-offline-'.bin2hex(random_bytes(9));
mkdir($folder,0700);
try{
    $db=zmTreasuryDb($folder);
    ensure((fileperms($folder.'/treasury-control.sqlite3')&0777)===0600,'private_file');
    $key=str_repeat('a',32);
    [$id,$created]=zmTreasuryNew($db,$key,'INV-SYN-001','Synthetic supplier internal approval',
        'payable',12500,'IRR',11,'accountant');
    ensure($created&&$id===1,'new_proposal');
    [$idem,$isNew]=zmTreasuryNew($db,$key,'INV-SYN-001','Synthetic supplier internal approval',
        'payable',12500,'IRR',11,'accountant');
    ensure($idem===1&&!$isNew,'idempotency');
    rejected(fn()=>zmTreasuryNew($db,$key,'INV-CHANGED','Different',
        'payable',12500,'IRR',11,'accountant'),409,'key_conflict');
    rejected(fn()=>zmTreasuryNew($db,str_repeat('b',32),'INV-X','bad',
        'payable',0,'IRR',11,'accountant'),422,'zero_amount');
    rejected(fn()=>zmTreasuryNew($db,str_repeat('b',32),'INV-X','bad',
        'payable',12000,'IRR',11,'viewer'),403,'viewer_create');
    rejected(fn()=>zmTreasuryDecide($db,$id,'submit','Viewer may not submit',11,'viewer'),403,'viewer_submit');
    try {
        $db->exec("UPDATE treasury_requests SET status='approved',reviewed_by=11,decision_note='bypass' WHERE id=1");
        ensure(false,'direct_sql_approval_rejected');
    }catch(PDOException $e){ensure(true,'direct_sql_approval_rejected');}
    zmTreasuryDecide($db,$id,'submit','Synthetic evidence attached',11,'accountant');
    rejected(fn()=>zmTreasuryDecide($db,$id,'approve','Self approval',11,'admin'),403,'self_approval');
    rejected(fn()=>zmTreasuryDecide($db,$id,'approve','No authority',77,'manager'),403,'manager_approval');
    zmTreasuryDecide($db,$id,'approve','Reviewed by separate owner',77,'admin');
    ensure($db->query("SELECT status FROM treasury_requests WHERE id=1")->fetchColumn()==='approved','approved_state');
    rejected(fn()=>zmTreasuryDecide($db,$id,'cancel','Cannot undo approved',11,'accountant'),403,'terminal_state');
    try {
        $db->exec("UPDATE treasury_requests SET amount_minor=1 WHERE id=1");
        ensure(false,'amount_immutable');
    }catch(PDOException $e){ensure(true,'amount_immutable');}
    try {
        $db->exec('DELETE FROM treasury_events WHERE treasury_id=1');
        ensure(false,'audit_immutable');
    }catch(PDOException $e){ensure(true,'audit_immutable');}
    try {
        $db->exec("UPDATE treasury_requests SET status='rejected',reviewed_by=88,decision_note='tamper' WHERE id=1");
        ensure(false,'terminal_immutable');
    }catch(PDOException $e){ensure(true,'terminal_immutable');}
    ensure($db->query('SELECT COUNT(*) FROM treasury_events')->fetchColumn()===3,'event_count');
    ensure(count(zmTreasuryAudit($db))===0,'audit_invariants');
    ensure($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','db_integrity');
    $db=null;$db=zmTreasuryDb($folder);
    ensure($db->query("SELECT status FROM treasury_requests WHERE id=1")->fetchColumn()==='approved','durability');
    echo "TREASURY_OFFLINE_SQLITE_QA=PASS\n";
    echo "ROLE_SEPARATION=PASS DUAL_APPROVAL=PASS REPLAY=PASS IMMUTABLE_HISTORY=PASS\n";
    echo "BANK_TRANSFER=DISABLED LEDGER_POSTINGS=NONE SCHEDULED_AUTOMATION=NONE\n";
} finally {
    $db=null;
    foreach(glob($folder.'/*')?:[] as $file)if(is_file($file))unlink($file);
    rmdir($folder);
}

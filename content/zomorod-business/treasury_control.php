<?php
declare(strict_types=1);
/**
 * Zomorod Melal treasury payment-request control, OFFLINE/internal only.
 * Never connects to any bank, changes a financial ledger, pays a supplier,
 * collects funds or treats approval as proof of a real transaction.
 */
function zmTreasuryReject(string $message,int $status=422):never {
    if(function_exists('bail'))bail($message,$status);
    throw new RuntimeException($message,$status);
}
function zmTreasuryDb(string $private):PDO {
    if(!is_dir($private)||is_link($private))throw new RuntimeException('Unsafe private treasury directory');
    $path=$private.'/treasury-control.sqlite3';
    if(is_link($path))throw new RuntimeException('Unsafe treasury database path');
    $old=umask(0077);
    try {
        $db=new PDO('sqlite:'.$path,null,null,[
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT=>12]);
        if(!chmod($path,0600))throw new RuntimeException('Unable to protect treasury file');
    }finally{umask($old);}
    $db->exec('PRAGMA busy_timeout=12000;PRAGMA foreign_keys=ON;');
    $db->exec("CREATE TABLE IF NOT EXISTS treasury_requests (
        id INTEGER PRIMARY KEY,
        request_key TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
        reference TEXT NOT NULL,
        purpose TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('payable','receivable')),
        amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
        currency TEXT NOT NULL CHECK(currency IN ('IRR','USD','EUR','AED')),
        requested_by INTEGER NOT NULL CHECK(requested_by>0),
        status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','submitted','approved','rejected','cancelled')),
        reviewed_by INTEGER,
        decision_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK ((status NOT IN ('approved','rejected')) OR
               (reviewed_by IS NOT NULL AND reviewed_by<>requested_by AND length(trim(decision_note))>0))
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS treasury_events (
        id INTEGER PRIMARY KEY,
        treasury_id INTEGER NOT NULL REFERENCES treasury_requests(id),
        actor_id INTEGER NOT NULL CHECK(actor_id>0),
        event TEXT NOT NULL,
        note TEXT NOT NULL,
        recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TRIGGER IF NOT EXISTS treasury_events_immutable_update
        BEFORE UPDATE ON treasury_events BEGIN SELECT RAISE(ABORT,'Treasury history immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS treasury_events_immutable_delete
        BEFORE DELETE ON treasury_events BEGIN SELECT RAISE(ABORT,'Treasury history immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS treasury_request_no_delete
        BEFORE DELETE ON treasury_requests BEGIN SELECT RAISE(ABORT,'Treasury request cannot be deleted'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS treasury_request_guard
        BEFORE UPDATE ON treasury_requests
        WHEN OLD.request_key<>NEW.request_key OR OLD.request_hash<>NEW.request_hash OR
             OLD.reference<>NEW.reference OR OLD.purpose<>NEW.purpose OR
             OLD.direction<>NEW.direction OR OLD.amount_minor<>NEW.amount_minor OR
             OLD.currency<>NEW.currency OR OLD.requested_by<>NEW.requested_by OR
             NOT (
                (OLD.status='draft' AND NEW.status IN ('submitted','cancelled')
                 AND NEW.reviewed_by IS NULL AND length(trim(NEW.decision_note))>0)
                OR
                (OLD.status='submitted' AND NEW.status IN ('approved','rejected')
                 AND NEW.reviewed_by IS NOT NULL AND NEW.reviewed_by<>OLD.requested_by
                 AND length(trim(NEW.decision_note))>0)
             )
        BEGIN SELECT RAISE(ABORT,'Forbidden treasury record mutation'); END");
    return $db;
}
function zmTreasuryNew(PDO $db,string $key,string $reference,string $purpose,
                      string $direction,int $amountMinor,string $currency,int $user,string $role):array {
    if(!in_array($role,['admin','accountant','manager'],true))zmTreasuryReject('Treasury access denied',403);
    if(!preg_match('/^[a-f0-9]{32}$/D',$key) || $user<=0 ||
       !in_array($direction,['payable','receivable'],true) ||
       !in_array($currency,['IRR','USD','EUR','AED'],true) ||
       $amountMinor<=0 || $amountMinor>100000000000000)zmTreasuryReject('Invalid treasury input');
    $reference=trim($reference);$purpose=trim($purpose);
    if($reference===''||strlen($reference)>100||$purpose===''||mbSafeLen($purpose)>750||
       preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u',$purpose))
        zmTreasuryReject('Invalid treasury text');
    $hash=hash('sha256',json_encode([$reference,$purpose,$direction,$amountMinor,$currency,$user],
            JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
    $db->beginTransaction();
    try{
        $s=$db->prepare('SELECT id,request_hash FROM treasury_requests WHERE request_key=?');
        $s->execute([$key]);$old=$s->fetch();
        if($old){
            if(!hash_equals((string)$old['request_hash'],$hash))
                zmTreasuryReject('Idempotency key reused for a different request',409);
            $db->commit();return [(int)$old['id'],false];
        }
        $db->prepare('INSERT INTO treasury_requests(request_key,request_hash,reference,purpose,direction,amount_minor,currency,requested_by) VALUES(?,?,?,?,?,?,?,?)')
            ->execute([$key,$hash,$reference,$purpose,$direction,$amountMinor,$currency,$user]);
        $id=(int)$db->lastInsertId();
        $db->prepare('INSERT INTO treasury_events(treasury_id,actor_id,event,note) VALUES(?,?,?,?)')
            ->execute([$id,$user,'created','Internal-only proposal; no transfer or accounting entry']);
        $db->commit();return [$id,true];
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmTreasuryDecide(PDO $db,int $id,string $action,string $reason,int $actor,string $role):void {
    if($id<=0||$actor<=0||!in_array($action,['submit','approve','reject','cancel'],true))
        zmTreasuryReject('Invalid treasury decision');
    if(!in_array($role,['admin','manager','accountant'],true))zmTreasuryReject('Access denied',403);
    $reason=trim($reason);
    if($reason===''||mbSafeLen($reason)>700)zmTreasuryReject('Decision reason required');
    $db->beginTransaction();
    try{
        $s=$db->prepare('SELECT id,status,requested_by FROM treasury_requests WHERE id=?');
        $s->execute([$id]);$old=$s->fetch();
        if(!$old)zmTreasuryReject('Treasury proposal not found',404);
        $creator=(int)$old['requested_by'];$status=(string)$old['status'];
        if(in_array($action,['submit','cancel'],true)){
            if($status!=='draft'||($actor!==$creator&&$role!=='admin'))
                zmTreasuryReject('Only creator or owner can submit/cancel draft',403);
        }elseif($status!=='submitted'||$role!=='admin'||$actor===$creator){
            zmTreasuryReject('Independent admin decision required',403);
        }
        $next=['submit'=>'submitted','approve'=>'approved','reject'=>'rejected','cancel'=>'cancelled'][$action];
        $reviewer=in_array($action,['approve','reject'],true)?$actor:null;
        $db->prepare('UPDATE treasury_requests SET status=?,reviewed_by=?,decision_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?')
            ->execute([$next,$reviewer,$reason,$id]);
        $db->prepare('INSERT INTO treasury_events(treasury_id,actor_id,event,note) VALUES(?,?,?,?)')
            ->execute([$id,$actor,$action,$reason]);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmTreasuryAudit(PDO $db):array {
    $r=[];
    foreach($db->query("SELECT r.id,r.status,r.requested_by,r.reviewed_by,COUNT(e.id) events
         FROM treasury_requests r LEFT JOIN treasury_events e ON e.treasury_id=r.id GROUP BY r.id") as $row){
        if((int)$row['events']<2&&$row['status']!=='draft')
            $r[]=['request'=>(int)$row['id'],'code'=>'MISSING_HISTORY'];
        if(in_array($row['status'],['approved','rejected'],true)&&
           ($row['reviewed_by']===null||(int)$row['reviewed_by']===(int)$row['requested_by']))
            $r[]=['request'=>(int)$row['id'],'code'=>'MISSING_INDEPENDENT_REVIEW'];
    }
    return $r;
}

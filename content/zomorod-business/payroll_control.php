<?php
declare(strict_types=1);
/** Private payroll proposal and dual-control approval.
 * Internal accrual estimates only. No payroll bank disbursements, tax filings,
 * legal pay-rate calculations or journal postings occur here.
 */
function zmPayrollDb(string $private): PDO {
    if (!is_dir($private) || is_link($private)) throw new RuntimeException('Unsafe private payroll directory');
    $path=$private.'/payroll-control.sqlite3';
    if (is_link($path)) throw new RuntimeException('Unsafe payroll database');
    $old=umask(0077);
    try {
        $db=new PDO('sqlite:'.$path,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>12]);
        if(!chmod($path,0600)) throw new RuntimeException('Could not secure payroll records');
    } finally {umask($old);}
    $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=12000');
    $db->exec("CREATE TABLE IF NOT EXISTS payroll_periods(
        id INTEGER PRIMARY KEY,
        period TEXT NOT NULL UNIQUE CHECK(length(period)=7),
        request_key TEXT NOT NULL UNIQUE,
        payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),
        currency TEXT NOT NULL CHECK(currency IN ('IRR','USD','EUR','AED')),
        state TEXT NOT NULL DEFAULT 'draft'
            CHECK(state IN ('draft','submitted','approved','rejected','cancelled')),
        gross_total INTEGER NOT NULL CHECK(gross_total>=0),
        deduction_total INTEGER NOT NULL CHECK(deduction_total>=0),
        net_total INTEGER NOT NULL CHECK(net_total>=0),
        requested_by INTEGER NOT NULL,
        reviewed_by INTEGER,
        review_reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS payroll_lines(
        id INTEGER PRIMARY KEY,
        period_id INTEGER NOT NULL REFERENCES payroll_periods(id),
        employee_ref TEXT NOT NULL,
        base_minor INTEGER NOT NULL CHECK(base_minor>=0),
        addition_minor INTEGER NOT NULL CHECK(addition_minor>=0),
        deduction_minor INTEGER NOT NULL CHECK(deduction_minor>=0),
        net_minor INTEGER NOT NULL CHECK(net_minor>=0),
        UNIQUE(period_id,employee_ref)
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS payroll_events(
        id INTEGER PRIMARY KEY,
        period_id INTEGER NOT NULL REFERENCES payroll_periods(id),
        actor_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_events_no_update BEFORE UPDATE ON payroll_events
        BEGIN SELECT RAISE(ABORT,'Payroll event history is immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_events_no_delete BEFORE DELETE ON payroll_events
        BEGIN SELECT RAISE(ABORT,'Payroll event history is immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_lines_no_update AFTER UPDATE ON payroll_lines
        BEGIN SELECT RAISE(ABORT,'Payroll lines are immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_lines_no_delete BEFORE DELETE ON payroll_lines
        BEGIN SELECT RAISE(ABORT,'Payroll lines are immutable'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_lines_locked_insert BEFORE INSERT ON payroll_lines
        WHEN (SELECT state FROM payroll_periods WHERE id=NEW.period_id)!='draft'
        BEGIN SELECT RAISE(ABORT,'Payroll period is locked'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_periods_no_delete BEFORE DELETE ON payroll_periods
        BEGIN SELECT RAISE(ABORT,'Payroll proposal deletion prohibited'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS payroll_periods_state_only BEFORE UPDATE ON payroll_periods
        WHEN OLD.period!=NEW.period OR OLD.request_key!=NEW.request_key
          OR OLD.payload_sha256!=NEW.payload_sha256 OR OLD.currency!=NEW.currency
          OR OLD.gross_total!=NEW.gross_total OR OLD.deduction_total!=NEW.deduction_total
          OR OLD.net_total!=NEW.net_total OR OLD.requested_by!=NEW.requested_by
          OR OLD.state IN ('approved','cancelled')
        BEGIN SELECT RAISE(ABORT,'Payroll record protected'); END");
    return $db;
}
function zmPayrollReject(string $message,int $code=422): never {
    if(function_exists('bail')) bail($message,$code);
    throw new RuntimeException($message,$code);
}
function zmPayrollCreate(PDO $db,string $key,string $period,string $currency,array $lines,int $actor): array {
    if(!preg_match('/^[0-9a-f]{32}$/D',$key) ||
       !preg_match('/^20[0-9]{2}-(?:0[1-9]|1[0-2])$/D',$period) ||
       !in_array($currency,['IRR','USD','EUR','AED'],true) ||
       $actor<1 || count($lines)<1 || count($lines)>100) zmPayrollReject('مشخصات دوره یا ردیف‌ها معتبر نیست.');
    $clean=[];$seen=[];$gross=0;$deductions=0;$net=0;
    foreach($lines as $row){
        if(!is_array($row) || array_keys($row)!==['employee_ref','base','addition','deduction'])
            zmPayrollReject('فیلدهای حقوق نامعتبر است.');
        $ref=trim((string)$row['employee_ref']);
        if(!preg_match('/^[A-Za-z0-9_-]{1,32}$/D',$ref) || isset($seen[$ref]))
            zmPayrollReject('شناسه کارمند تکراری یا نامعتبر است.');
        $seen[$ref]=true;
        foreach(['base','addition','deduction'] as $k){
            if(!is_int($row[$k]) || $row[$k]<0 || $row[$k]>1000000000000)
                zmPayrollReject('مبلغ حقوق یا کسورات نامعتبر است.');
        }
        $g=$row['base']+$row['addition'];
        if($row['deduction']>$g)zmPayrollReject('کسورات از حقوق بیشتر است.');
        $v=$g-$row['deduction'];
        $gross+=$g;$deductions+=$row['deduction'];$net+=$v;
        if($gross>100000000000000 || $deductions>100000000000000 || $net>100000000000000)
            zmPayrollReject('جمع دوره بیش از سقف است.');
        $clean[]=[$ref,$row['base'],$row['addition'],$row['deduction'],$v];
    }
    usort($clean,static fn($a,$b)=>strcmp($a[0],$b[0]));
    $hash=hash('sha256',json_encode([$period,$currency,$clean,$actor],JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
    $db->beginTransaction();
    try {
        $q=$db->prepare('SELECT id,payload_sha256 FROM payroll_periods WHERE request_key=?');
        $q->execute([$key]);$previous=$q->fetch();
        if($previous){
            if(!hash_equals((string)$previous['payload_sha256'],$hash))
                zmPayrollReject('شناسه تکراری با محتوای متفاوت.',409);
            $db->commit();return [(int)$previous['id'],false];
        }
        $db->prepare('INSERT INTO payroll_periods(period,request_key,payload_sha256,currency,gross_total,deduction_total,net_total,requested_by) VALUES(?,?,?,?,?,?,?,?)')
            ->execute([$period,$key,$hash,$currency,$gross,$deductions,$net,$actor]);
        $id=(int)$db->lastInsertId();
        $stmt=$db->prepare('INSERT INTO payroll_lines(period_id,employee_ref,base_minor,addition_minor,deduction_minor,net_minor) VALUES(?,?,?,?,?,?)');
        foreach($clean as $row)$stmt->execute([$id,...$row]);
        $db->prepare('INSERT INTO payroll_events(period_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$actor,'draft_created','پیشنهاد داخلی؛ هیچ پرداخت یا ارسال مالیاتی انجام نشده است.']);
        $db->commit();return [$id,true];
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmPayrollDecision(PDO $db,int $id,string $decision,int $actor,string $role,string $reason):void {
    if($id<1||$actor<1||!in_array($decision,['submit','approve','reject','cancel'],true))
        zmPayrollReject('درخواست نامعتبر است.');
    $reason=trim($reason);
    if($reason===''||mbSafeLen($reason)>900)zmPayrollReject('مبنای تصمیم باید ثبت شود.');
    $db->beginTransaction();
    try{
        $s=$db->prepare('SELECT * FROM payroll_periods WHERE id=?');$s->execute([$id]);$p=$s->fetch();
        if(!$p)zmPayrollReject('دوره پیدا نشد.',404);
        $owner=(int)$p['requested_by'];$isAdmin=$role==='admin';
        if($decision==='submit' && ($p['state']!=='draft'||($actor!==$owner&&!$isAdmin)))
            zmPayrollReject('ارسال دوره مجاز نیست.',403);
        if($decision==='cancel' && ($p['state']!=='draft'||($actor!==$owner&&!$isAdmin)))
            zmPayrollReject('لغو دوره مجاز نیست.',403);
        if(in_array($decision,['approve','reject'],true)){
            if($p['state']!=='submitted'||!$isAdmin||$actor===$owner)
                zmPayrollReject('دوره باید توسط مدیر مستقل بررسی شود.',403);
        }
        $state=['submit'=>'submitted','approve'=>'approved','reject'=>'rejected','cancel'=>'cancelled'][$decision];
        $reviewer=in_array($decision,['approve','reject'],true)?$actor:null;
        $db->prepare('UPDATE payroll_periods SET state=?,reviewed_by=?,review_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?')
            ->execute([$state,$reviewer,$reason,$id]);
        $db->prepare('INSERT INTO payroll_events(period_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$actor,$decision,$reason]);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmPayrollAudit(PDO $db): array {
    $findings=[];
    foreach($db->query('SELECT p.id,p.net_total,p.gross_total,p.deduction_total,COUNT(l.id) n,COALESCE(SUM(l.net_minor),0) net,COALESCE(SUM(l.base_minor+l.addition_minor),0) gross,COALESCE(SUM(l.deduction_minor),0) deducted FROM payroll_periods p LEFT JOIN payroll_lines l ON p.id=l.period_id GROUP BY p.id') as $row){
        if((int)$row['n']===0||(int)$row['net']!==(int)$row['net_total']||
           (int)$row['gross']!==(int)$row['gross_total']||
           (int)$row['deducted']!==(int)$row['deduction_total'])
            $findings[]=['period_id'=>(int)$row['id'],'code'=>'TOTAL_MISMATCH'];
    }
    return $findings;
}

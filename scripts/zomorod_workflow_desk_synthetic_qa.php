<?php
declare(strict_types=1);
/** Offline synthetic tests: no employee, invoice, purchase or company DB writes. */
error_reporting(E_ALL);
$GLOBALS['test_actor']=11;$GLOBALS['test_role']='manager';
function actor():int{return $GLOBALS['test_actor'];}
function role():string{return $GLOBALS['test_role'];}
function authorize(string $access):void{if($access==='view'&&!in_array(role(),['viewer','accountant','manager','admin'],true))bail('unauthorized',403);}
function bail(string $text,int $code=422):never{throw new RuntimeException($text,$code);}
function mbSafeLen(string $s):int{return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}
function money(int $a):string{return number_format($a/100,2,'.',',');}
function esc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function cents(string $s):int{if(!preg_match('/^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/',$s))bail('amount');$a=explode('.',$s);return (int)$a[0]*100+(int)str_pad($a[1]??'',2,'0');}
function q(PDO $db,string $sql,array $args=[]):array{$s=$db->prepare($sql);$s->execute($args);return $s->fetchAll(PDO::FETCH_ASSOC);}
function req(string $key,string $fallback=''):string{return (string)($GLOBALS['post'][$key]??$fallback);}
function formBegin(string $name):void{echo '<form action="'.esc($name).'">';}
function expect(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('FLOW_QA_FAILED='.$name);}
function denied(callable $fn,int $expected,string $test):void{
    try{$fn();}catch(RuntimeException $e){expect($e->getCode()===$expected,$test.'_code');return;}
    throw new RuntimeException('FLOW_QA_FAILED='.$test.'_not_blocked');
}
require __DIR__.'/../content/zomorod-business/workflow_desk.php';
$dir=sys_get_temp_dir().'/zm-flow-test-'.bin2hex(random_bytes(12));
mkdir($dir,0700);
try{
    $db=zmFlowDb($dir);
    $file=$dir.'/company-workflow.sqlite3';
    expect(is_file($file) && (fileperms($file)&0777)===0600,'private_sqlite_permissions');
    $key='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    [$id,$created]=zmFlowCreate($db,$key,'procurement','خرید آزمایشی','صرفاً آزمون گردش‌کار',150000,'IRR','normal',11);
    expect($created && $id===1,'create_procurement');
    expect($db->query('SELECT risk FROM requests WHERE id=1')->fetchColumn()==='high_impact','monetary_purchase_auto_high_risk');
    [$duplicate,$same]=zmFlowCreate($db,$key,'procurement','خرید آزمایشی','صرفاً آزمون گردش‌کار',150000,'IRR','normal',11);
    expect($duplicate===$id && !$same,'request_key_replay_idempotent');
    denied(fn()=>zmFlowCreate($db,$key,'contract','CONFLICT','New',150000,'IRR','normal',11),409,'same_key_changed_request');
    zmFlowTransition($db,$id,'submit','مدرک اولیه آماده است',11,'manager');
    denied(fn()=>zmFlowTransition($db,$id,'approve','اختیار ندارم',11,'manager'),403,'manager_cannot_approve');
    denied(fn()=>zmFlowTransition($db,$id,'approve','خودتأییدی ممنوع',11,'admin'),403,'same_actor_cannot_approve_sensitive');
    zmFlowTransition($db,$id,'reject','مستندات کافی نیست',17,'admin');
    expect($db->query('SELECT state FROM requests WHERE id=1')->fetchColumn()==='rejected','rejection');
    zmFlowTransition($db,$id,'revise','مدارک تکمیلی',11,'manager');
    zmFlowTransition($db,$id,'submit','مجدداً ارسال شد',11,'manager');
    zmFlowTransition($db,$id,'approve','صرفاً تصمیم داخلی؛ بدون پرداخت یا قرارداد',17,'admin');
    expect($db->query('SELECT state FROM requests WHERE id=1')->fetchColumn()==='approved','two_person_sensitive_approval');
    denied(fn()=>zmFlowTransition($db,$id,'cancel','نباید بسته شود',11,'manager'),409,'terminal_state_immutable');
    [$leave]=zmFlowCreate($db,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','leave','مرخصی آزمایشی','دو روز کاری',0,'IRR','normal',11);
    zmFlowTransition($db,$leave,'submit','به کارتابل ارسال شد',11,'manager');
    zmFlowTransition($db,$leave,'approve','تأیید داخلی',11,'admin');
    expect($db->query('SELECT COUNT(*) FROM request_events')->fetchColumn()==='10','append_only_audit_events');
    denied(fn()=>zmFlowCreate($db,'cccccccccccccccccccccccccccccccc','contract','<script>','bad',-1,'IRR','normal',11),422,'negative_amount');
    denied(fn()=>zmFlowCreate($db,'cccccccccccccccccccccccccccccccc','unknown','Title','Detail',0,'IRR','normal',11),422,'invalid_type');
    $GLOBALS['test_role']='viewer';
    denied(fn()=>zmFlowAdminOrManager(),403,'viewer_denied_write');
    ob_start();zmFlowRender($db);$out=(string)ob_get_clean();
    expect(str_contains($out,'کارتابل یکپارچه'),'render_view');
    $GLOBALS['test_role']='admin';
    [$x]=zmFlowCreate($db,'dddddddddddddddddddddddddddddddd','administration','<script>alert(1)</script>','بررسی آزمون',0,'IRR','normal',11);
    ob_start();zmFlowRender($db);$html=(string)ob_get_clean();
    expect(str_contains($html,'&lt;script&gt;')&&!str_contains($html,'<script>'),'xss_escaped');
    expect($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','db_integrity');
    $db=null;
    $db=zmFlowDb($dir);
    expect($db->query('SELECT COUNT(*) FROM requests')->fetchColumn()==='3','persistence_after_reopen');
    echo "ZOMOROD_WORKFLOW_QA=PASS\n";
    echo "HIGH_RISK_SEPARATION=PASS IDPOTENCY=PASS WORKFLOW_AUDIT=PASS\n";
    echo "ROLE_CONTROL=PASS PRIVATE_DB_PERMISSIONS=PASS XSS_ESCAPING=PASS\n";
    echo "BANK_AND_CONTRACT_EXECUTION=NONE RECURRING_TASK=NOT_CREATED\n";
}finally{
    $db=null;
    foreach(glob($dir.'/*')?:[] as $f){if(is_file($f))unlink($f);}
    rmdir($dir);
}

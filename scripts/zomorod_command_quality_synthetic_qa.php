<?php
declare(strict_types=1);
/** Synthetic-only acceptance and evidence gate regression; never use live data. */
error_reporting(E_ALL);
function actor(): int { return 42; }
function role(): string { return $GLOBALS['fake_role']??'admin'; }
function bail(string $message,int $code=422): never { throw new RuntimeException($message,$code); }
function req(string $key,string $default=''): string { return (string)($GLOBALS['post'][$key]??$default); }
function mbSafeLen(string $s): int { return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s); }
function money(int $n): string { return number_format($n/100,2,'.',','); }
function esc(mixed $s): string { return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function formBegin(string $action): void {echo '<form method="post">'.esc($action);}
function q(PDO $db,string $query,array $params=[]): array {
    $s=$db->prepare($query);$s->execute($params);return $s->fetchAll(PDO::FETCH_ASSOC);
}
function check(bool $ok,string $case): void { if(!$ok) throw new RuntimeException('REGRESSION_FAILURE='.$case); }
function shouldReject(callable $fn,int $code,string $test): void {
    try {$fn();}catch(RuntimeException $e){check($e->getCode()===$code,$test.'_wrong_code');return;}
    throw new RuntimeException('REGRESSION_FAILURE='.$test.'_was_accepted');
}
require __DIR__.'/../content/zomorod-business/command_center.php';
$dir=sys_get_temp_dir().'/zm-cc-quality-'.bin2hex(random_bytes(10));
mkdir($dir,0700);
try {
    $db=zmCcDb($dir);
    $key='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    check(zmCcCreate($db,$key,null,'company','Synthetic oversight','No external action','high',42),'task_created');
    $id=(int)$db->lastInsertId();
    check($id>0,'task_identity');
    shouldReject(fn()=>zmCcQualityPlan($db,$id,'invalid','Plan','Acceptance',42),422,'risk_whitelist');
    zmCcQualityPlan($db,$id,'high_impact','Deliverable requires human check','Evidence reviewed against acceptance criteria',42);
    shouldReject(fn()=>zmCcQualityPlan($db,$id,'read_only','Override','Override',42),409,'immutable_plan');
    zmCcTransition($db,$id,'in_progress','Work initiated',42);
    shouldReject(fn()=>zmCcTransition($db,$id,'done','Pretend done',42),409,'unreviewed_completion_gate');
    shouldReject(fn()=>zmCcQualityEvidence($db,$id,'http://example.com/data',42),422,'insecure_evidence_url');
    shouldReject(fn()=>zmCcQualityEvidence($db,$id,'https://user:password@example.com/private',42),422,'embedded_credentials');
    zmCcQualityEvidence($db,$id,'https://github.com/example/repo/issues/123',42);
    check($db->query('SELECT review_state FROM task_quality WHERE task_id=1')->fetchColumn()==='submitted','evidence_submitted');
    shouldReject(fn()=>zmCcTransition($db,$id,'done','No review yet',42),409,'submitted_not_complete');
    zmCcQualityReview($db,$id,false,'Evidence does not prove completion',42);
    shouldReject(fn()=>zmCcTransition($db,$id,'done','Rejected but closing',42),409,'rejected_not_complete');
    zmCcQualityEvidence($db,$id,'https://github.com/example/repo/actions/runs/100',42);
    zmCcQualityReview($db,$id,true,'Reviewed evidence and accepted deliverable',42);
    zmCcTransition($db,$id,'done','Accepted and closed with evidence',42);
    check($db->query('SELECT state FROM tasks WHERE id=1')->fetchColumn()==='done','completion_after_review');
    shouldReject(fn()=>zmCcQualityEvidence($db,$id,'https://github.com/example/repo/issues/999',42),409,'done_cannot_resubmit');
    check((int)$db->query("SELECT COUNT(*) FROM task_events WHERE task_id=1")->fetchColumn()===9,'append_only_event_sequence');
    $GLOBALS['fake_role']='viewer';
    shouldReject(fn()=>zmCcQualityHandle($db,'cc_review',42),403,'review_restricted');
    $GLOBALS['fake_role']='admin';
    ob_start();zmCcQualityWidgets($db,$id,['state'=>'done']);$ui=ob_get_clean();
    check(str_contains($ui,'تأیید مدیر'),'approved_shown');
    $f=new PDO('sqlite:'.$dir.'/command-center.sqlite3');
    check($f->query('SELECT review_state FROM task_quality WHERE task_id=1')->fetchColumn()==='approved','durable_review');
    echo "COMMAND_QUALITY_SYNTHETIC_QA=PASS\n";
    echo "RISK_CLASSIFICATION=PASS ACCEPTANCE_GATE=PASS REJECT_RESUBMIT_APPROVE=PASS\n";
    echo "OWNER_ONLY_REVIEW=PASS EVIDENCE_URL_VALIDATION=PASS EVENT_AUDIT=PASS\n";
    echo "FINANCIAL_ACTIONS=NONE RECURRING_SCHEDULE=NOT_CREATED\n";
}finally{
    $f=null;$db=null;
    foreach(glob($dir.'/*')?:[] as $path){if(is_file($path))unlink($path);}
    rmdir($dir);
}

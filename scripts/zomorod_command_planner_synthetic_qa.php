<?php
declare(strict_types=1);
/** Rule-based owner operations planner: synthetic-only acceptance tests. */
function actor(): int {return 10;}
function role(): string {return $GLOBALS['fake_role']??'admin';}
function bail(string $message,int $code=422): never {throw new RuntimeException($message,$code);}
function req(string $name,string $default=''): string{return (string)($GLOBALS['fake_post'][$name]??$default);}
function mbSafeLen(string $s):int{return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}
function money(int $v):string{return number_format($v/100,2,'.',',');}
function esc(mixed $s):string{return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function formBegin(string $a):void{echo '<form>'.esc($a).'</form>';}
function q(PDO $db,string $sql,array $values=[]):array{$s=$db->prepare($sql);$s->execute($values);return $s->fetchAll(PDO::FETCH_ASSOC);}
function must(bool $c,string $label):void{if(!$c)throw new RuntimeException('TEST_FAILURE='.$label);}
require __DIR__.'/../content/zomorod-business/command_center.php';
$dir=sys_get_temp_dir().'/zm-ops-'.bin2hex(random_bytes(8));
mkdir($dir,0700);
try{
    $db=zmCcDb($dir);
    $k=['11111111111111111111111111111111','22222222222222222222222222222222','33333333333333333333333333333333'];
    must(zmCcCreate($db,$k[0],null,'finance','Urgent <untrusted> invoice','Manual reconciliation','critical',10),'seed_1');
    must(zmCcCreate($db,$k[1],null,'projects','Evidence waiting','Requires review','normal',10),'seed_2');
    must(zmCcCreate($db,$k[2],null,'inventory','Stock issue','Needs monitoring','high',10),'seed_3');
    zmCcTransition($db,1,'blocked','Waiting for internal documents',10);
    zmCcQualityPlan($db,2,'high_impact','Project report','Signed result',10);
    zmCcTransition($db,2,'in_progress','Working',10);
    zmCcQualityEvidence($db,2,'https://github.com/example/repo/issues/10',10);
    zmCcQualityPlan($db,3,'read_only','Read-only stock review','Inventory verified',10);
    $snapshot=zmCcOpsSnapshot($db,'2026-10-29');
    must($snapshot['examined']===3,'examined_count');
    must($snapshot['counts']['blocked']===1,'blocked_count');
    must($snapshot['counts']['missing_plan']===1,'missing_plans_count');
    must($snapshot['counts']['awaiting_review']===1,'submitted_count');
    must($snapshot['counts']['high_impact']===1,'high_impact_count');
    must($snapshot['counts']['queued']===1 && $snapshot['counts']['in_progress']===1,'lifecycle_counts');
    must($snapshot['items'][0]['id']===1,'risk_priority_order');
    must($snapshot['items'][0]['action']==='ثبت خروجی مورد انتظار، طبقه ریسک و معیار پذیرش','missing_plan_next_action');
    must($snapshot['items'][1]['id']===3,'second_priority_order');
    must($snapshot['items'][2]['id']===2 && $snapshot['items'][2]['review']==='submitted','review_queue');
    $before=(int)$db->query('SELECT COUNT(*) FROM task_events')->fetchColumn();
    ob_start();zmCcOpsRender($db);$markup=(string)ob_get_clean();
    must(str_contains($markup,'برنامه‌ریز عملیاتی مدیرعامل'),'screen_render');
    must(str_contains($markup,'&lt;untrusted&gt;'),'html_escaped');
    must(!str_contains($markup,'<untrusted>'),'not_raw_html');
    must((int)$db->query('SELECT COUNT(*) FROM task_events')->fetchColumn()===$before,'read_only_render');
    $GLOBALS['fake_role']='viewer';
    $denied=false;
    try{zmCcOpsRender($db);}catch(RuntimeException $e){$denied=$e->getCode()===403;}
    must($denied,'admin_only');
    echo "COMMAND_PLANNER_SYNTHETIC_QA=PASS\n";
    echo "PRIORITIZATION=PASS MISSING_PLAN_DETECTION=PASS REVIEW_QUEUE=PASS\n";
    echo "OWNER_AUTHORIZATION=PASS READ_ONLY_RENDERING=PASS HTML_ESCAPING=PASS\n";
    echo "SCHEDULE=NOT_CREATED EXECUTION=NOT_ENABLED\n";
}finally{
    $db=null;
    foreach(glob($dir.'/*')?:[] as $f){if(is_file($f))unlink($f);}
    rmdir($dir);
}

<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/site_agents.php';
require_once dirname(__DIR__).'/site_agent_workforce.php';
function must(bool $c,string $reason):void{if(!$c)throw new RuntimeException($reason);}
$root=sys_get_temp_dir().'/zm-site-work-'.bin2hex(random_bytes(6));
must(mkdir($root,0700),'temp dir');
try{
 $db=zmAgentDb($root);
 zmWorkInitialize($db);
 must((int)$db->query('SELECT COUNT(*) FROM agents')->fetchColumn()===11,'registry');
 $seen=[];
 for($generation=1;$generation<=100;$generation++){
   // Distinct 100 in-memory HTML/HTTP fixtures; never production network.
   $mode=$generation%10;
   $head='<html lang="fa"><head>'.
      ($mode===1?'':'<title>زمرد ملل | بررسی تخصصی '.$generation.'</title>').
      ($mode===2?'':'<meta name="description" content="شرح علمی این صفحه">').
      '</head><body>'.
      ($mode===3?'':'<h1>عنوان تخصصی صفحه '.$generation.'</h1>').
      ($mode===4?'<h1>تکرار</h1>':'').
      ($mode===5?'':'<a href="/research/">تحقیقات</a>').
      str_repeat('متن معتبر پژوهشی ',10).'</body></html>';
   $fixture=[
      'status'=>$mode===6?0:($mode===7?302:200),
      'type'=>$mode===8?'application/octet-stream':'text/html',
      'body'=>$mode===9?'short':$head,
      'error'=>'',
   ];
   $report=zmWorkAssess('/research/',$fixture);
   must($report['status']!==''&&strlen($report['sha'])===64,'report schema');
   if($mode>=6)must($report['status']==='blocked','invalid page did not fail closed '.$generation);
   else must($report['status']==='review','valid 200 refused '.$generation);
   if($mode===3)must(in_array('h1_count_not_one',$report['findings']['issues'],true),'h1 gate');
   if($mode===1)must(in_array('missing_title',$report['findings']['issues'],true),'title gate');
   if($mode===2)must(in_array('missing_meta_description',$report['findings']['issues'],true),'description gate');
   if($mode===4)must(in_array('h1_count_not_one',$report['findings']['issues'],true),'duplicate h1 gate');
   $seen[$generation]=hash('sha256',json_encode([$generation,$fixture['status'],$fixture['body'],$report],JSON_THROW_ON_ERROR));
   $cycle=zmWorkCycle($db,static fn(string $u):array=>$fixture,2);
   must(count($cycle)===2,'two real private database writes');
   foreach($cycle as $p)must($p['artifact']>0,'missing work ledger ID');
   echo 'ZM_SITE_WORK_GENERATION_TEST='.$generation.' passed proof='.$seen[$generation]."\n";
 }
 must(count(array_unique($seen))===100,'unique fixtures');
 must((int)$db->query('SELECT COUNT(*) FROM site_work_outputs')->fetchColumn()===200,'durable outputs');
 $app=zmWorkDashboard($db);
 must(str_contains($app,'200'),'dashboard totals');
 $before=(int)$db->query('SELECT COUNT(*) FROM site_work_generation_evidence')->fetchColumn();
 try{
  $db->exec("INSERT INTO site_work_generation_evidence
   (agent_code,candidate_sha256,baseline_sha256,benchmark_before,benchmark_after,tests_passed,accepted)
   VALUES ('master','same','same',60,60,0,1)");
  throw new RuntimeException('Proof gate allowed fake promotion');
 }catch(PDOException $e){
   must(str_contains($e->getMessage(),'constraint'),'wrong rejection reason');
 }
 must((int)$db->query('SELECT COUNT(*) FROM site_work_generation_evidence')->fetchColumn()===$before,'failed proof should not be logged');
 foreach(['https://outside.example/','//evil.example','/../etc/passwd','/a?redirect=external'] as $unsafe){
  try{zmWorkSafePath($unsafe);throw new RuntimeException('Unsafe path accepted');}
  catch(InvalidArgumentException $e){}
 }
 echo "ZM_SITE_WORKER_100_EVIDENCE_CASES=passed\n";
 echo "ZM_SITE_WORKER_DB_TEST_OUTPUTS=200\n";
 echo "ZM_SITE_WORKER_UNPROVEN_GENERATION_PROMOTION=blocked\n";
}finally{
 $db=null;
 foreach(glob($root.'/*')?:[] as $f)@unlink($f);
 @rmdir($root);
}

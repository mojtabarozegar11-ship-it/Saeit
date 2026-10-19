<?php
declare(strict_types=1);
/*
 * One hundred distinct OFFLINE regression scenarios, not a claim that
 * one hundred separately proven autonomous code generations were built.
 * Never calls production or touches the live database.
 */
require_once __DIR__.'/../site_agents.php';
function ensure(bool $ok,string $msg): void {
    if(!$ok)throw new RuntimeException('GATE_FAIL: '.$msg);
}
$root=sys_get_temp_dir().'/zm-site-generation-harness-'.bin2hex(random_bytes(6));
if(!mkdir($root,0700))throw new RuntimeException('Failed to create temp folder');
try {
    $db=zmAgentDb($root);
    ensure((int)$db->query('SELECT COUNT(*) FROM agents')->fetchColumn()===11,'eleven agents seeded');
    $agents=$db->query('SELECT code FROM agents ORDER BY code')->fetchAll(PDO::FETCH_COLUMN);
    ensure(in_array('master',$agents,true),'master present');
    $roles=array_values(array_filter($agents,fn($s)=>$s!=='master'));
    ensure(count($roles)===10,'ten site monitors');
    $calls=0;$observed=[];
    for($generation=1;$generation<=100;$generation++){
        // Alternate failure classes to prove fail-closed behavior in ALL roles.
        $mode=$generation%5;
        $faultAgent=$roles[($generation-1)%count($roles)];
        $probe=function(string $url)use($mode,$faultAgent,&$calls,$db):array {
            $calls++;
            ensure(str_starts_with($url,'https://zomorodmelal.ir/'),'same-origin only');
            $path=parse_url($url,PHP_URL_PATH);
            $st=$db->prepare('SELECT code FROM agents WHERE check_path=?');
            $st->execute([$path]);
            $code=$st->fetchColumn();
            // Several agents may share pages; determine faulty URL by role's
            // expected configured path but keep deterministic fixture.
            $paths=['master'=>'/','content'=>'/knowledge/','seo'=>'/search/',
              'commerce'=>'/store/','agriculture'=>'/agriculture/',
              'research'=>'/research/','economic'=>'/economy/',
              'weather'=>'/weather/','quality'=>'/about/',
              'media'=>'/news/','security'=>'/business/'];
            if($url!=='https://zomorodmelal.ir'.$paths[$faultAgent]){
                return ['http'=>200,'bytes'=>140,'content_type'=>'text/html','error'=>''];
            }
            if($mode===0)return ['http'=>200,'bytes'=>180,'content_type'=>'text/html','error'=>''];
            if($mode===1)return ['http'=>0,'bytes'=>0,'content_type'=>'','error'=>'simulated transport error'];
            if($mode===2)return ['http'=>302,'bytes'=>200,'content_type'=>'text/html','error'=>''];
            if($mode===3)return ['http'=>200,'bytes'=>1,'content_type'=>'text/html','error'=>''];
            return ['http'=>200,'bytes'=>180,'content_type'=>'application/octet-stream','error'=>''];
        };
        $before=(int)$db->query('SELECT COUNT(*) FROM runs')->fetchColumn();
        $results=zmAgentCycle($db,null,$probe);
        ensure(count($results)===11,'all agents invoked generation '.$generation);
        $after=(int)$db->query('SELECT COUNT(*) FROM runs')->fetchColumn();
        ensure($after-$before===11,'one audit row per agent');
        $by=[];foreach($results as $entry)$by[$entry[0]]=$entry;
        ensure(count($by)===11,'no duplicate agent');
        $degraded=$mode!==0;
        ensure(($by['master'][1]==='ok')===(!$degraded),'master aggregate fails closed '.$generation);
        if($degraded)ensure(($by[$faultAgent][1]??'ok')!=='ok','fault acknowledged '.$generation);
        foreach($results as [$code,$status,$http]){
            ensure(in_array($code,$agents,true),'unknown agent');
            if($status==='ok')ensure($http===200,'no false HTTP success');
        }
        $digest=hash('sha256',json_encode(['g'=>$generation,'mode'=>$mode,
            'fault'=>$faultAgent,'statuses'=>array_column($results,1),
            'master'=>$by['master'][1]],JSON_THROW_ON_ERROR));
        $observed[]=$digest;
        echo 'SITE_AGENT_GENERATION_GATE='.$generation.' passed proof='.$digest."\n";
    }
    ensure(count(array_unique($observed))===100,'unique generation test evidence');
    ensure((int)$db->query('SELECT COUNT(*) FROM runs')->fetchColumn()===1100,'all 1100 results recorded');
    $callsBefore=$calls;
    $db->exec("UPDATE agents SET check_path='//evil.example/path' WHERE code='agriculture'");
    $x=zmAgentCycle($db,'agriculture',function($url)use(&$calls){$calls++;return ['http'=>200,'bytes'=>1000,'content_type'=>'text/html'];});
    ensure($x[0][1]==='error','malicious path rejected');
    ensure($callsBefore===$calls,'unsafe path did not make network request');
    $db->exec("UPDATE agents SET check_path='/agriculture/' WHERE code='agriculture'");
    ensure(str_contains(zmAgentChart([['status'=>'ok'],['status'=>'error']]),'<svg'),'truthful chart');
    echo 'ZOMOROD_SITE_AGENT_100_OFFLINE_GATES=passed role_count=11 proofs=100 sample_results=1100'."\n";
    echo 'PRODUCTION_CODE_GENERATIONS_VERIFIED=not_claimed'."\n";
}finally{
    $db=null;
    foreach(glob($root.'/*')?:[] as $p)if(is_file($p))@unlink($p);
    @rmdir($root);
}

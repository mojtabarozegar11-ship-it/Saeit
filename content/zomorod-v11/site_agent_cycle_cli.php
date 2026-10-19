<?php
declare(strict_types=1);
/** Site-scoped private CLI scheduler. No payments, public edits, external sites, VPS factory or AI provider calls. */
if(PHP_SAPI!=='cli'){http_response_code(404);exit(2);}
if(count($argv)!==1){fwrite(STDERR,"Usage: site-agent-cycle-cli (no arguments)\n");exit(2);}
$private=__DIR__;
if(is_link($private.'/site_agents.php')||is_link($private.'/site_agent_workforce.php'))exit(10);
require_once $private.'/site_agents.php';
require_once $private.'/site_agent_workforce.php';
$lockFile=$private.'/.site-worker.lock';
$lock=fopen($lockFile,'c');
if(!$lock || !flock($lock,LOCK_EX|LOCK_NB)){
    echo "ZM_SITE_AGENT_WORKER=already_running\n";exit(0);
}
try {
    $db=zmAgentDb($private);
    $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=10000');
    $all=zmAgentCycle($db);
    $review=zmWorkCycle($db,null,2);
    if(count($all)!==11)throw new RuntimeException('Expected exactly 11 site-agent checks');
    if(count($review)<1)throw new RuntimeException('No site-specific evidence work produced');
    $errors=array_values(array_filter($all,fn($row)=>$row[1]!=='ok'));
    $names=array_map(fn($row)=>$row[0],$errors);
    echo 'ZM_SITE_AGENT_CYCLE_CHECKS='.count($all)."\n";
    echo 'ZM_SITE_AGENT_CYCLE_PRODUCED_EVIDENCE='.count($review)."\n";
    echo 'ZM_SITE_AGENT_CYCLE_DEGRADED_ROLES='.json_encode($names,JSON_THROW_ON_ERROR)."\n";
    echo 'ZM_SITE_AGENT_CYCLE_COMPLETED=yes'."\n";
    exit(count($errors)?3:0);
} catch(Throwable $e) {
    fwrite(STDERR,'ZM_SITE_AGENT_CYCLE_FAILED_CLASS='.get_class($e)."\n");
    exit(5);
} finally {
    flock($lock,LOCK_UN);
    fclose($lock);
}

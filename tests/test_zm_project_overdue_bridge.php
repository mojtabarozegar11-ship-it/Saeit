<?php
declare(strict_types=1);
$root=sys_get_temp_dir().'/zm-cmd-project-'.bin2hex(random_bytes(6));
if(!mkdir($root,0700))throw new RuntimeException('temp directory');
$p=$root.'/management.sqlite3';
$db=new PDO('sqlite:'.$p,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$db->exec("CREATE TABLE zm_project_milestones (id INTEGER PRIMARY KEY,project_id INTEGER,title TEXT,due_date TEXT,state TEXT)");
$db->exec("INSERT INTO zm_project_milestones VALUES(25,194,'Internal milestone due','2026-01-01','todo')");
unset($db);chmod($p,0600);
$control=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$control->exec('CREATE TABLE tasks (request_key TEXT PRIMARY KEY,source_key TEXT,workstream TEXT,title TEXT,detail TEXT,priority TEXT)');
function zmCcCreate(PDO $db,string $key,?string $source,string $workstream,string $title,string $detail,string $priority,int $uid):bool {
 $s=$db->prepare('INSERT OR IGNORE INTO tasks VALUES(?,?,?,?,?,?)');
 $s->execute([$key,$source,$workstream,$title,$detail,$priority]);
 return $s->rowCount()===1;
}
require dirname(__DIR__).'/content/zomorod-business/command_integrations.php';
$a=zmCcScanBridges($control,0,$root);
$b=zmCcScanBridges($control,0,$root);
$tasks=$control->query('SELECT source_key,workstream,title FROM tasks')->fetchAll(PDO::FETCH_ASSOC);
if($a['created']!==1||$b['created']!==0||count($tasks)!==1||$tasks[0]['workstream']!=='projects')
 throw new RuntimeException('SCAN_IDEMPOTENCY_FAILED '.json_encode([$a,$b,$tasks]));
echo "PROJECT_OVERDUE_CREATED=".$a['created']." SECOND_RUN=".$b['created']." TASKS=".count($tasks).PHP_EOL;
unlink($p);rmdir($root);

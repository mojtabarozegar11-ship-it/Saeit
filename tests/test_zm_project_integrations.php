<?php
declare(strict_types=1);
$role='admin';$actor=1;$payload=[];
function role():string{global $role;return $role;}
function actor():int{global $actor;return $actor;}
function req(string $k,string $default=''):string{global $payload;return trim((string)($payload[$k]??$default));}
function bail(string $v,int $code=422):never{throw new RuntimeException($v,$code);}
function authorize(string $scope):void{}
function esc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function today():string{return '2026-11-03';}
function money(int $v):string{return number_format($v/100,2);}
function q(PDO $db,string $sql,array $vars=[]):array{$s=$db->prepare($sql);$s->execute($vars);return $s->fetchAll(PDO::FETCH_ASSOC);}
function audit(PDO $db,string $verb,string $subject,int $id=0):void{
  $stmt=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');
  $stmt->execute([actor(),$verb,$subject,$id]);}
function zmPmClean(string $s,int $limit=800):string{
 $s=trim($s);if(!$s||strlen($s)>$limit)bail('Invalid note');return $s;}
function formBegin(string $v):void{echo '<form method="post"><input name="csrf" value="synthetic-only"><input type="hidden" name="action" value="'.esc($v).'">';}
require dirname(__DIR__).'/content/zomorod-business/project_integrations.php';
$d=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$d->exec('PRAGMA foreign_keys=ON');
$d->exec('CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT,active INTEGER,username TEXT)');
$d->exec('CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT,state TEXT,owner TEXT,budget INTEGER)');
$d->exec('CREATE TABLE documents(id INTEGER PRIMARY KEY,title TEXT)');
$d->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_no TEXT)');
$d->exec('CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT)');
$d->exec('CREATE TABLE inventory(id INTEGER PRIMARY KEY,name TEXT)');
$d->exec('CREATE TABLE employees(id INTEGER PRIMARY KEY,fullname TEXT)');
$d->exec('CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,verb TEXT,subject TEXT,entity_id INTEGER)');
$d->exec("INSERT INTO users VALUES(1,'admin',1,'admin'),(2,'manager',1,'manager'),(3,'viewer',1,'viewer'),(4,'accountant',1,'accountant')");
$d->exec("INSERT INTO projects VALUES(1,'Test project','planned','Test',0),(2,'Second project','paused','Test',0)");
$d->exec("INSERT INTO documents VALUES(1,'Evidence document')");
$d->exec("INSERT INTO invoices VALUES(1,'Synthetic INV')");
$d->exec("INSERT INTO journal_entries VALUES(1,'Synthetic JV')");
zmPiSchema($d);
$dir=sys_get_temp_dir().'/zm-project-link-'.bin2hex(random_bytes(5));
mkdir($dir,0700);
function satellite(string $dir,string $n,string $table,string $columns,string $sql):void{
 $p=$dir.'/'.$n;
 $c=new PDO('sqlite:'.$p);
 $c->exec("CREATE TABLE ".$table."(".$columns.")");
 $c->exec($sql);unset($c);chmod($p,0600);
}
satellite($dir,'command-center.sqlite3','tasks','id INTEGER PRIMARY KEY,title TEXT,state TEXT',"INSERT INTO tasks VALUES(7,'Review stage','queued')");
satellite($dir,'company-workflow.sqlite3','requests','id INTEGER PRIMARY KEY,title TEXT,state TEXT',"INSERT INTO requests VALUES(8,'Approval document','submitted')");
satellite($dir,'industry-operations.sqlite3','industry_items','id INTEGER PRIMARY KEY,title TEXT,status TEXT',"INSERT INTO industry_items VALUES(9,'Private operations','received')");
satellite($dir,'site_agents.sqlite3','agents','code TEXT PRIMARY KEY,title TEXT,enabled INTEGER',"INSERT INTO agents VALUES('agent42','Internal agent',1)");
satellite($dir,'chatgpt_reports_archive.sqlite3','reports','report_code TEXT PRIMARY KEY',"INSERT INTO reports VALUES('05-0033')");
$pass=0;
function ok(bool $ok,string $label):void{global $pass;if(!$ok)throw new RuntimeException('FAIL '.$label);$pass++;echo "PASS $label\n";}
function blocked(callable $fn,int $code,string $label):void{
 $bad=false;try{$fn();}catch(RuntimeException $e){$bad=$e->getCode()===$code;}
 ok($bad,$label);
}
$payload=['project_id'=>'1','source'=>'document','reference'=>'1','reason'=>'Internal note and real synthetic document'];
zmPiHandle($d,$dir,'project_link');
ok((int)$d->query('SELECT count(*) FROM zm_project_links')->fetchColumn()===1,'linked existing document');
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),409,'duplicate link rejected');
$payload['project_id']='2';
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),409,'same document not linked twice across projects');
$payload=['project_id'=>'1','source'=>'task','reference'=>'7','reason'=>'Task association validated from satellite'];
zmPiHandle($d,$dir,'project_link');
ok((int)$d->query('SELECT count(*) FROM zm_project_links')->fetchColumn()===2,'command task link accepted');
$payload['reference']='999';
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),404,'nonexistent satellite target rejected');
$payload=['project_id'=>'1','source'=>'workflow','reference'=>'8','reason'=>'Approved trace'];zmPiHandle($d,$dir,'project_link');
$payload=['project_id'=>'1','source'=>'industry','reference'=>'9','reason'=>'Operational link only'];zmPiHandle($d,$dir,'project_link');
$payload=['project_id'=>'1','source'=>'agent','reference'=>'agent42','reason'=>'Software supervision'];zmPiHandle($d,$dir,'project_link');
$payload=['project_id'=>'1','source'=>'report','reference'=>'05-0033','reason'=>'Cycle report, unverified self-report'];zmPiHandle($d,$dir,'project_link');
ok((int)$d->query('SELECT count(*) FROM zm_project_links')->fetchColumn()===6,'multiple cross-system links');
$role='manager';$actor=2;
$payload=['project_id'=>'1','source'=>'invoice','reference'=>'1','reason'=>'Financial relation'];
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),403,'manager cannot link financial invoice');
$payload=['project_id'=>'1','source'=>'agent','reference'=>'agent42','reason'=>'Supervisory relation'];
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),403,'manager cannot link agent');
$payload=['project_id'=>'1','source'=>'document','reference'=>'1','reason'=>'Existing document'];
// Existing document is known duplicate but role must be checked first.
$role='viewer';$actor=3;
blocked(fn()=>zmPiHandle($d,$dir,'project_link'),403,'viewer cannot link');
$role='manager';$actor=2;
$payload=['project_id'=>'1','title'=>'Review project deadline','due_date'=>'2026-11-20'];
zmPiHandle($d,$dir,'project_milestone');
ok((int)$d->query('SELECT count(*) FROM zm_project_milestones')->fetchColumn()===1,'milestone created');
ok((int)$d->query('SELECT count(*) FROM zm_project_milestone_events')->fetchColumn()===1,'creation event recorded');
$payload['due_date']='2026-02-30';
blocked(fn()=>zmPiHandle($d,$dir,'project_milestone'),422,'invalid due date denied');
$payload=['project_id'=>'1','milestone_id'=>'1','expected_state'=>'todo','next_state'=>'in_progress','note'=>'Work begun in internal synthetic memory'];
zmPiHandle($d,$dir,'project_milestone_state');
ok($d->query('SELECT state FROM zm_project_milestones')->fetchColumn()==='in_progress','milestone progresses');
blocked(fn()=>zmPiHandle($d,$dir,'project_milestone_state'),409,'stale transition blocked');
$payload=['project_id'=>'1','milestone_id'=>'1','expected_state'=>'in_progress','next_state'=>'done','note'=>'Documented and internally closed'];
zmPiHandle($d,$dir,'project_milestone_state');
ok($d->query('SELECT state FROM zm_project_milestones')->fetchColumn()==='done','milestone closure recorded');
blocked(fn()=>zmPiHandle($d,$dir,'project_milestone_state'),409,'closed milestone cannot reenter workflow');
ok((int)$d->query('SELECT count(*) FROM zm_project_milestone_events')->fetchColumn()===3,'history append-only');
ob_start();$_GET['project_id']='1';zmPiRender($d,$dir);$html=ob_get_clean();
ok(str_contains($html,'پرونده یکپارچه پروژه'),'project view renders');
ok(str_contains($html,'Evidence document'),'linked existing document renders');
ob_start();zmPiCalendar($d);$cal=ob_get_clean();
ok(str_contains($cal,'تقویم عملیات'),'calendar renders');
ok($d->query('PRAGMA integrity_check')->fetchColumn()==='ok','test database integrity');
ok($d->query('PRAGMA foreign_key_check')->fetchAll()===[],'test foreign keys');
ok((int)$d->query('SELECT count(*) FROM audit_events')->fetchColumn()===9,'audit records retained for all writes');
foreach(glob($dir.'/*.sqlite3') as $f)unlink($f);rmdir($dir);
echo "TOTAL_PASSED=$pass\n";

<?php
declare(strict_types=1);
$ROLE='admin';$ID=1;$POST=[];
function role():string {global $ROLE;return $ROLE;}
function actor():int {global $ID;return $ID;}
function req(string $name,string $default=''):string {global $POST;return trim((string)($POST[$name]??$default));}
function bail(string $msg,int $code=422):never {throw new RuntimeException($msg,$code);}
function authorize(string $perm):void {}
function esc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function money(int $v):string{return number_format($v/100,2);}
function formBegin(string $name):void {echo '<form>'.esc($name);}
function q(PDO $db,string $sql,array $arg=[]):array {$s=$db->prepare($sql);$s->execute($arg);return $s->fetchAll(PDO::FETCH_ASSOC);}
function one(PDO $db,string $sql,array $arg=[]):mixed{$s=$db->prepare($sql);$s->execute($arg);return $s->fetchColumn();}
require dirname(__DIR__).'/content/zomorod-business/project_control.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
 PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);$db->exec('PRAGMA foreign_keys=ON');
$db->exec("CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT,active INTEGER,username TEXT)");
$db->exec("CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT,owner TEXT,state TEXT,budget INTEGER)");
$db->exec("CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,verb TEXT,subject TEXT,entity_id INTEGER)");
$db->exec("INSERT INTO users VALUES(1,'admin',1,'owner'),(2,'manager',1,'mgr'),(3,'viewer',1,'viewer')");
$db->exec("INSERT INTO projects VALUES(1,'case one','team','planned',0),(2,'case two','team','paused',0)");
zmPmSchema($db);
$pass=0;
function check(bool $b,string $label):void {global $pass;if(!$b)throw new RuntimeException('FAIL: '.$label);$pass++;echo "PASS $label\n";}
function blocked(callable $f,int $code,string $name):void {
 $ok=false;try{$f();}catch(RuntimeException $e){$ok=$e->getCode()===$code;}
 check($ok,$name);
}
$POST=['project_id'=>'1','expected_state'=>'planned','next_state'=>'active','reason'=>'documented internal management decision'];
zmPmHandle($db,'project_transition');
check($db->query("SELECT state FROM projects WHERE id=1")->fetchColumn()==='active','admin planned_to_active');
check((int)$db->query('SELECT count(*) FROM zm_project_events')->fetchColumn()===1,'immutable transition event');
check((int)$db->query("SELECT count(*) FROM audit_events WHERE verb='transition'")->fetchColumn()===1,'transition audit event');
blocked(fn()=>zmPmHandle($db,'project_transition'),409,'stale state blocked');
check($db->query("SELECT state FROM projects WHERE id=1")->fetchColumn()==='active','stale leaves state unchanged');
$ROLE='viewer';$ID=3;
blocked(fn()=>zmPmHandle($db,'project_transition'),403,'viewer blocked');
$ROLE='manager';$ID=2;
$POST=['project_id'=>'1','category'=>'progress','progress_pct'=>'35','description'=>'Reported progress, requires independent verification'];
zmPmHandle($db,'project_update');
check($db->query('SELECT progress_pct FROM zm_project_updates')->fetchColumn()===35,'progress note recorded');
check((int)$db->query("SELECT count(*) FROM audit_events WHERE verb='note'")->fetchColumn()===1,'note audit event');
$POST=['project_id'=>'2','category'=>'blocker','progress_pct'=>'','description'=>'Awaiting review evidence'];
zmPmHandle($db,'project_update');
check((int)$db->query('SELECT count(*) FROM zm_project_updates')->fetchColumn()===2,'blocker note recorded');
$POST=['project_id'=>'2','category'=>'progress','progress_pct'=>'111','description'=>'Invalid percent'];
blocked(fn()=>zmPmHandle($db,'project_update'),422,'invalid progress blocked');
$POST=['project_id'=>'2','expected_state'=>'paused','next_state'=>'done','reason'=>'Invalid jump'];
blocked(fn()=>zmPmHandle($db,'project_transition'),409,'invalid lifecycle transition blocked');
$ROLE='admin';$ID=1;
$POST=['project_id'=>'1','expected_state'=>'active','next_state'=>'done','reason'=>'Internal administrative closure, not physical proof'];
zmPmHandle($db,'project_transition');
check($db->query("SELECT state FROM projects WHERE id=1")->fetchColumn()==='done','closure valid');
$POST=['project_id'=>'1','expected_state'=>'done','next_state'=>'active','reason'=>'Attempt reopen'];
blocked(fn()=>zmPmHandle($db,'project_transition'),409,'closed project cannot silently reopen');
check((int)$db->query('SELECT count(*) FROM zm_project_events')->fetchColumn()===2,'only valid transitions recorded');
ob_start();zmPmRender($db);$html=ob_get_clean();
check(str_contains($html,'داشبورد مدیریت پروژه‌های شرکت'),'management page renders');
check(str_contains($html,'تاریخچه پیشرفت و موانع'),'history visible');
check($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','sqlite integrity');
check($db->query('PRAGMA foreign_key_check')->fetchAll()===[],'foreign keys intact');
echo "TOTAL_PASSED=$pass\n";

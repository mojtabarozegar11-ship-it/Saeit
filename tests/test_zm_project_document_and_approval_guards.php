<?php
declare(strict_types=1);
$ROLE='admin';$ACTOR=1;$POST=[];
function role():string{global $ROLE;return $ROLE;}
function actor():int{global $ACTOR;return $ACTOR;}
function req(string $k,string $fallback=''):string{global $POST;return trim((string)($POST[$k]??$fallback));}
function bail(string $msg,int $http=422):never{throw new RuntimeException($msg,$http);}
function authorize(string $p):void{}
function esc(mixed $s):string{return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function today():string{return '2026-11-03';}
function money(int $n):string{return number_format($n/100,2);}
function q(PDO $db,string $sql,array $args=[]):array{$st=$db->prepare($sql);$st->execute($args);return $st->fetchAll(PDO::FETCH_ASSOC);}
function one(PDO $db,string $sql,array $args=[]):mixed{$st=$db->prepare($sql);$st->execute($args);return $st->fetchColumn();}
function formBegin(string $action):void{echo '<form><input name="action" value="'.esc($action).'">';}
function audit(PDO $db,string $verb,string $subject,int $id=0):void{
  $st=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');$st->execute([actor(),$verb,$subject,$id]);
}
require dirname(__DIR__).'/content/zomorod-business/project_control.php';
require dirname(__DIR__).'/content/zomorod-business/project_integrations.php';
$pdo=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$pdo->exec('PRAGMA foreign_keys=ON');
$pdo->exec('CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT,active INTEGER,username TEXT)');
$pdo->exec('CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT,state TEXT,owner TEXT,budget INTEGER)');
$pdo->exec('CREATE TABLE documents(id INTEGER PRIMARY KEY,title TEXT,category TEXT,body TEXT,created_by INTEGER)');
$pdo->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_no TEXT)');
$pdo->exec('CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT)');
$pdo->exec('CREATE TABLE journal_lines(id INTEGER PRIMARY KEY)');
$pdo->exec('CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY)');
$pdo->exec('CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,verb TEXT,subject TEXT,entity_id INTEGER)');
$pdo->exec("INSERT INTO users VALUES(1,'admin',1,'admin'),(2,'manager',1,'manager'),(3,'viewer',1,'viewer'),(4,'accountant',1,'accountant')");
$pdo->exec("INSERT INTO projects VALUES(1,'ZM-001 | مصوب | Research proposal','planned','Research',0),(2,'ZM-002 | مصوب | Production proposal','planned','Company',0),(3,'ZM-005 | ردشده - فقط بایگانی؛ غیرقابل اجرا','paused','Archive',0),(4,'ZM-046 | تعیین‌تکلیف نشده؛ غیرمصوب | Pending proposal','paused','Company',0)");
$pdo->exec("INSERT INTO documents VALUES(1,'Common memo','مکاتبات','Shared text',1)");
$pdo->exec("INSERT INTO invoices VALUES(1,'INVOICE-NO-PAYMENT')");
$pdo->exec("INSERT INTO journal_entries VALUES(1,'JOURNAL-NO-PAYMENT')");
zmPmSchema($pdo);zmPiSchema($pdo);
$passed=0;
function check(bool $ok,string $label):void{global $passed;if(!$ok)throw new RuntimeException('FAIL '.$label);++$passed;echo "PASS $label\n";}
function rejected(callable $fn,int $status,string $label):void{$seen=false;try{$fn();}catch(RuntimeException $e){$seen=$e->getCode()===$status;}check($seen,$label);}
check(zmPmIsArchiveOnly('ZM-005 | ردشده - فقط بایگانی؛ غیرقابل اجرا'),'archive marker detected');
check(!zmPmIsArchiveOnly('ZM-008 | مصوب | پژوهش'),'approved marker not misclassified');
check(zmPmIsApproved('ZM-008 | مصوب | پژوهش'),'explicit approved marker accepted');
check(!zmPmIsApproved('ZM-046 | تعیین‌تکلیف نشده؛ غیرمصوب'),'unapproved not treated as approved');
$dir='/home/zomorod2/.backups/zm-management-docflow-20261103';
$POST=['project_id'=>'1','source'=>'document','reference'=>'1','reason'=>'Shared real context'];
zmPiHandle($pdo,$dir,'project_link');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_links')===1,'first project document link');
$POST['project_id']='2';zmPiHandle($pdo,$dir,'project_link');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_links')===2,'common memo can serve two projects');
rejected(fn()=>zmPiHandle($pdo,$dir,'project_link'),409,'duplicate within same project rejected');
$POST=['project_id'=>'1','source'=>'invoice','reference'=>'1','reason'=>'Financial attribution reference only'];
zmPiHandle($pdo,$dir,'project_link');
$POST['project_id']='2';
rejected(fn()=>zmPiHandle($pdo,$dir,'project_link'),409,'same invoice cannot allocate twice');
$POST=['project_id'=>'1','source'=>'journal','reference'=>'1','reason'=>'Single financial project'];
zmPiHandle($pdo,$dir,'project_link');
$POST['project_id']='2';
rejected(fn()=>zmPiHandle($pdo,$dir,'project_link'),409,'same journal cannot allocate twice');
$POST=['project_id'=>'1','title'=>'Internal scientific correspondence','category'=>'مکاتبات','body'=>'A real project may use an approved note in the live app'];
zmPiHandle($pdo,$dir,'project_document');
check((int)one($pdo,'SELECT COUNT(*) FROM documents')===2,'document created in transaction');
check((int)one($pdo,"SELECT COUNT(*) FROM zm_project_links WHERE source='document' AND reference='2' AND project_id=1")===1,'new document linked atomically');
check((int)one($pdo,'SELECT COUNT(*) FROM journal_lines')===0,'no finance journal lines written');
check((int)one($pdo,'SELECT COUNT(*) FROM invoice_payments')===0,'no payment entries written');
$POST=['project_id'=>'1','title'=>'','category'=>'مکاتبات','body'=>'Not enough title'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_document'),422,'invalid document refused');
check((int)one($pdo,'SELECT COUNT(*) FROM documents')===2,'document write rolled back on validation');
$POST=['project_id'=>'4','expected_state'=>'paused','next_state'=>'active','reason'=>'No approval cannot start'];
rejected(fn()=>zmPmHandle($pdo,'project_transition'),409,'unapproved project cannot activate');
$POST=['project_id'=>'4','title'=>'No production until approved','due_date'=>'2026-11-15'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_milestone'),409,'unapproved project cannot create operational milestone');
$POST=['project_id'=>'4','source'=>'journal','reference'=>'1','reason'=>'No financial allocation'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_link'),409,'unapproved project cannot receive financial attribution');
$POST=['project_id'=>'3','title'=>'Unauthorized internal memo','category'=>'مکاتبات','body'=>'Not allowed'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_document'),409,'archived project cannot create new documents');
$POST=['project_id'=>'3','title'=>'Unauthorized deadline','due_date'=>'2026-11-10'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_milestone'),409,'archived project cannot create milestones');
$POST=['project_id'=>'3','source'=>'invoice','reference'=>'1','reason'=>'Prohibited financial attachment'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_link'),409,'archived project cannot receive finance link');
$POST=['project_id'=>'3','source'=>'document','reference'=>'1','reason'=>'Historic reference only'];
zmPiHandle($pdo,$dir,'project_link');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_links WHERE project_id=3')===1,'archive reference to historical memo allowed');
$POST=['project_id'=>'3','expected_state'=>'paused','next_state'=>'active','reason'=>'Must refuse activation'];
rejected(fn()=>zmPmHandle($pdo,'project_transition'),409,'rejected project cannot activate');
$POST=['project_id'=>'3','category'=>'progress','progress_pct'=>'90','description'=>'Must refuse progress'];
rejected(fn()=>zmPmHandle($pdo,'project_update'),409,'rejected project cannot report new execution progress');
$POST=['project_id'=>'3','category'=>'decision','progress_pct'=>'','description'=>'Archival decision log only'];
zmPmHandle($pdo,'project_update');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_updates')===1,'rejected project permits archival decision notes');
$ROLE='viewer';$ACTOR=3;
$POST=['project_id'=>'1','title'=>'Viewer cannot create','category'=>'مکاتبات','body'=>'Blocked'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_document'),403,'viewer cannot create connected docs');
$ROLE='admin';$ACTOR=1;
$_GET['project_id']='3';ob_start();zmPiRender($pdo,$dir);$html=ob_get_clean();
check(str_contains($html,'فقط بایگانی'),'archived dossier clearly flagged');
check(!str_contains($html,'name="action" value="project_document"'),'archived dossier hides document write form');
check($pdo->query('PRAGMA integrity_check')->fetchColumn()==='ok','isolated database valid');
check($pdo->query('PRAGMA foreign_key_check')->fetchAll()===[],'isolated references valid');
echo "TOTAL_PASSED=$passed\n";

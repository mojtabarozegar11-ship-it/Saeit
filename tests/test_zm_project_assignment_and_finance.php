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
require dirname(__DIR__).'/content/zomorod-business/project_ops.php';
$pdo=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$pdo->exec('PRAGMA foreign_keys=ON');
$pdo->exec('CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT,active INTEGER,username TEXT)');
$pdo->exec('CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT,state TEXT,owner TEXT,budget INTEGER)');
$pdo->exec('CREATE TABLE documents(id INTEGER PRIMARY KEY,title TEXT,category TEXT,body TEXT,created_by INTEGER)');
$pdo->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_no TEXT,posted_entry INTEGER)');
$pdo->exec('CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT,doc_date TEXT)');
$pdo->exec('CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER,account_id INTEGER,debit INTEGER,credit INTEGER,currency TEXT)');
$pdo->exec('CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY)');
$pdo->exec('CREATE TABLE ledger_accounts(id INTEGER PRIMARY KEY,code TEXT,name TEXT,type TEXT,active INTEGER)');
$pdo->exec('CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,verb TEXT,subject TEXT,entity_id INTEGER)');
$pdo->exec("INSERT INTO users VALUES(1,'admin',1,'admin'),(2,'manager',1,'manager'),(3,'viewer',1,'viewer'),(4,'accountant',1,'accountant')");
$pdo->exec("INSERT INTO projects VALUES(1,'ZM-001 | مصوب | Research proposal','planned','Research',0),(2,'ZM-002 | مصوب | Production proposal','planned','Company',0),(3,'ZM-005 | ردشده - فقط بایگانی؛ غیرقابل اجرا','paused','Archive',0),(4,'ZM-046 | تعیین‌تکلیف نشده؛ غیرمصوب | Pending proposal','paused','Company',0)");
$pdo->exec("INSERT INTO documents VALUES(1,'Common memo','مکاتبات','Shared text',1)");
$pdo->exec("INSERT INTO invoices VALUES(1,'INVOICE-NO-PAYMENT',1)");
$pdo->exec("INSERT INTO journal_entries VALUES(1,'JOURNAL-NO-PAYMENT','2026-11-01')");
zmPmSchema($pdo);zmPiSchema($pdo);zmOpsSchema($pdo);
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
// New tests: real-user assignment, reassignment trace, and posted journal accounting.
$POST=['project_id'=>'1','title'=>'First review task','due_date'=>'2026-11-15','assigned_user_id'=>'2'];
zmPiHandle($pdo,$dir,'project_milestone');
check((int)one($pdo,'SELECT assigned_user_id FROM zm_project_milestone_assignments WHERE milestone_id=1')===2,'milestone assigns real manager user');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_milestone_assignment_events')===1,'initial assignment event');
$POST=['project_id'=>'1','milestone_id'=>'1','assigned_user_id'=>'1','note'=>'Reassign to owner for review'];
zmOpsTransfer($pdo);
check((int)one($pdo,'SELECT assigned_user_id FROM zm_project_milestone_assignments WHERE milestone_id=1')===1,'reassignment changes responsible user');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_milestone_assignment_events')===2,'reassignment creates audit event');
rejected(fn()=>zmOpsTransfer($pdo),409,'duplicate assignment blocked');
$POST=['project_id'=>'1','milestone_id'=>'1','assigned_user_id'=>'3','note'=>'Cannot assign viewer'];
rejected(fn()=>zmOpsTransfer($pdo),409,'viewer account not assignable');
$POST=['project_id'=>'1','milestone_id'=>'1','assigned_user_id'=>'999','note'=>'No fictitious staff'];
rejected(fn()=>zmOpsTransfer($pdo),409,'nonexistent assignee blocked');
$POST=['project_id'=>'3','milestone_id'=>'1','assigned_user_id'=>'1','note'=>'Wrong parent'];
rejected(fn()=>zmOpsTransfer($pdo),404,'cannot move milestone from different project');
$POST=['project_id'=>'1','milestone_id'=>'1','expected_state'=>'todo','next_state'=>'in_progress','note'=>'Internal workflow progress'];
zmPiHandle($pdo,$dir,'project_milestone_state');
$POST=['project_id'=>'1','milestone_id'=>'1','expected_state'=>'in_progress','next_state'=>'done','note'=>'Internal task closure'];
zmPiHandle($pdo,$dir,'project_milestone_state');
$POST=['project_id'=>'1','milestone_id'=>'1','assigned_user_id'=>'2','note'=>'Closed task'];
rejected(fn()=>zmOpsTransfer($pdo),409,'closed milestone cannot reassign');
$POST=['project_id'=>'1','title'=>'Bad assignee task','due_date'=>'2026-12-01','assigned_user_id'=>'999'];
rejected(fn()=>zmPiHandle($pdo,$dir,'project_milestone'),409,'invalid new assignee causes atomic rollback');
check((int)one($pdo,'SELECT COUNT(*) FROM zm_project_milestones')===1,'invalid assignee never leaves orphan milestone');
$pdo->exec("INSERT INTO ledger_accounts VALUES(1,'5100','Operating expense','expense',1),(2,'1011','Bank','asset',1),(3,'4000','Revenue','income',1),(4,'1100','Receivable','asset',1)");
$pdo->exec("INSERT INTO journal_lines VALUES(1,1,1,25000,0,'IRR'),(2,1,2,0,25000,'IRR')");
$ROLE='admin';$ACTOR=1;
ob_start();zmOpsFinanceReport($pdo,1);$financial=ob_get_clean();
check(str_contains($financial,'250.00'),'posted expense attributed by direct journal and invoice only once');
check(str_contains($financial,'اسناد دارای انتساب متعارض که از تجمیع حذف شدند: <strong>0</strong>'),'no conflict with consistent dual links');
check((int)one($pdo,'SELECT COUNT(*) FROM invoice_payments')===0,'no payments created by finance reporting');
$pdo->exec("INSERT INTO invoices VALUES(2,'CONFLICTING-INVOICE',1)");
$POST=['project_id'=>'2','source'=>'invoice','reference'=>'2','reason'=>'Conflicting attribution fixture'];
zmPiHandle($pdo,$dir,'project_link');
ob_start();zmOpsFinanceReport($pdo,1);$financialConflict=ob_get_clean();
check(str_contains($financialConflict,'اسناد دارای انتساب متعارض که از تجمیع حذف شدند: <strong>1</strong>'),'conflicting financial attributions identified');
check(!str_contains($financialConflict,'250.00'),'conflicted journal excluded from project totals');
$ROLE='manager';$ACTOR=2;
rejected(fn()=>zmOpsFinanceReport($pdo,null),403,'manager without finance access refused');
$ROLE='viewer';$ACTOR=3;
rejected(fn()=>zmOpsFinanceReport($pdo,null),403,'viewer refused financial detail');
$ROLE='admin';$ACTOR=1;
ob_start();zmOpsAssignmentSection($pdo,1,true);$assignmentHtml=ob_get_clean();
check(str_contains($assignmentHtml,'مسئولیت و ارجاع اقدامات پروژه'),'responsibility UI rendered');
check(str_contains($assignmentHtml,'تاریخچه مسئولیت‌های ثبت‌شده'),'assignment history UI rendered');
check($pdo->query('PRAGMA integrity_check')->fetchColumn()==='ok','full regression database integrity');
check($pdo->query('PRAGMA foreign_key_check')->fetchAll()===[],'full regression foreign keys');
$POST=['project_id'=>'1','title'=>'Overdue review action','due_date'=>'2026-10-20','assigned_user_id'=>'2'];
zmPiHandle($pdo,$dir,'project_milestone');
$ROLE='admin';$ACTOR=1;ob_start();zmOpsAssignmentsDesk($pdo);$ownerQueue=ob_get_clean();
check(str_contains($ownerQueue,'Overdue review action'),'admin can see assigned overdue action');
check(str_contains($ownerQueue,'دارای سررسید گذشته: <strong>1</strong>'),'admin overdue count accurate');
$ROLE='manager';$ACTOR=2;ob_start();zmOpsAssignmentsDesk($pdo);$managerQueue=ob_get_clean();
check(str_contains($managerQueue,'Overdue review action'),'assigned manager sees own task');
check(str_contains($managerQueue,'دارای سررسید گذشته: <strong>1</strong>'),'manager overdue count parameter binding correct');
$ROLE='viewer';$ACTOR=3;ob_start();zmOpsAssignmentsDesk($pdo);$viewerQueue=ob_get_clean();
check(!str_contains($viewerQueue,'Overdue review action'),'unassigned viewer sees no private tasks of others');
$ROLE='admin';$ACTOR=1;
echo "TOTAL_PASSED=$passed\n";

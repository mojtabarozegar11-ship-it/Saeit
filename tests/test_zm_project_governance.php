<?php
declare(strict_types=1);
$ROLE='admin';$ACTOR=1;$FORM=[];
function role():string{global $ROLE;return $ROLE;}
function actor():int{global $ACTOR;return $ACTOR;}
function req(string $x,string $fallback=''):string{global $FORM;return trim((string)($FORM[$x]??$fallback));}
function bail(string $s,int $status=422):never{throw new RuntimeException($s,$status);}
function authorize(string $x):void{}
function esc(mixed $x):string{return htmlspecialchars((string)$x,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function money(int $n):string{return number_format($n/100,2);}
function formBegin(string $s):void{echo '<form><input name="action" value="'.esc($s).'">';}
function q(PDO $db,string $sql,array $args=[]):array{$x=$db->prepare($sql);$x->execute($args);return $x->fetchAll(PDO::FETCH_ASSOC);}
function one(PDO $db,string $sql,array $args=[]):mixed{$x=$db->prepare($sql);$x->execute($args);return $x->fetchColumn();}
function audit(PDO $db,string $verb,string $subject,int $id=0):void{$x=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');$x->execute([actor(),$verb,$subject,$id]);}
require dirname(__DIR__).'/content/zomorod-business/project_control.php';
require dirname(__DIR__).'/content/zomorod-business/project_integrations.php';
require dirname(__DIR__).'/content/zomorod-business/project_governance.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$db->exec('PRAGMA foreign_keys=ON');
$db->exec('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT,role TEXT,active INTEGER)');
$db->exec('CREATE TABLE projects(id INTEGER PRIMARY KEY,title TEXT,state TEXT)');
$db->exec('CREATE TABLE documents(id INTEGER PRIMARY KEY,title TEXT,body TEXT)');
$db->exec('CREATE TABLE audit_events(id INTEGER PRIMARY KEY,user_id INTEGER,verb TEXT,subject TEXT,entity_id INTEGER)');
$db->exec("INSERT INTO users VALUES(1,'Admin A','admin',1),(2,'Admin B','admin',1),(3,'Manager','manager',1),(4,'Viewer','viewer',1),(5,'Dormant','admin',0)");
$db->exec("INSERT INTO projects VALUES(1,'ZM-101 | مصوب | Research','planned'),(2,'ZM-102 | بررسی | Still unapproved','paused'),(3,'ZM-103 | ردشده - فقط بایگانی','paused')");
$db->exec("INSERT INTO documents VALUES(1,'Approved source evidence','Source text unchanged'),(2,'Unlinked evidence','Not linked')");
zmPmSchema($db);zmPiSchema($db);zmGovSchema($db);
$db->exec("INSERT INTO zm_project_links(project_id,source,reference,reason,created_by) VALUES (1,'document','1','Real evidence association',1)");
$pass=0;
function ok(bool $condition,string $name):void{global $pass;if(!$condition)throw new RuntimeException('TEST_FAILED: '.$name);++$pass;echo "PASS ".$name."\n";}
function denied(callable $call,int $code,string $name):void{$yes=false;try{$call();}catch(RuntimeException $e){$yes=$e->getCode()===$code;}ok($yes,$name);}
$FORM=['project_id'=>'1','kind'=>'execution','subject'=>'Approval for operational start','justification'=>'Reviewed objective and source documents','evidence_doc_id'=>'1'];
zmGovHandle($db,'project_approval_submit');
ok((int)one($db,'SELECT COUNT(*) FROM zm_project_approval_cases')===1,'one request submitted');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_events WHERE action='submitted'")===1,'submission event immutable');
ok(!zmGovHasExecutionClearance($db,1),'submission does not grant start permission');
$FORM=['project_id'=>'1','expected_state'=>'planned','next_state'=>'active','reason'=>'Attempt before independent review'];
denied(fn()=>zmPmHandle($db,'project_transition'),409,'active transition blocked before independent approval');
$FORM=['project_id'=>'1','kind'=>'execution','subject'=>'Approval for operational start','justification'=>'Reviewed objective and source documents','evidence_doc_id'=>'1'];
denied(fn()=>zmGovHandle($db,'project_approval_submit'),409,'duplicate open case rejected');
$FORM['evidence_doc_id']='2';
denied(fn()=>zmGovHandle($db,'project_approval_submit'),409,'unlinked evidence rejected');
$FORM=['project_id'=>'2','kind'=>'execution','subject'=>'Unapproved start','justification'=>'No owner approval','evidence_doc_id'=>'1'];
denied(fn()=>zmGovHandle($db,'project_approval_submit'),409,'unapproved plan cannot request execution');
$FORM=['project_id'=>'3','kind'=>'documentation','subject'=>'Archived request','justification'=>'Prohibited','evidence_doc_id'=>'1'];
denied(fn()=>zmGovHandle($db,'project_approval_submit'),409,'rejected plan cannot request review');
$FORM=['case_id'=>'1','decision'=>'approved','decision_note'=>'Self approval disallowed'];
denied(fn()=>zmGovHandle($db,'project_approval_decide'),403,'requester cannot independently approve execution');
$ROLE='manager';$ACTOR=3;
denied(fn()=>zmGovHandle($db,'project_approval_decide'),403,'manager cannot approve final decision');
$ROLE='admin';$ACTOR=5;
denied(fn()=>zmGovHandle($db,'project_approval_decide'),403,'inactive admin cannot decide');
$ROLE='admin';$ACTOR=2;
zmGovHandle($db,'project_approval_decide');
ok(zmGovHasExecutionClearance($db,1),'independent admin approval grants clearance');
$db->exec("UPDATE documents SET body='Unauthorized post-approval change' WHERE id=1");
ok(!zmGovHasExecutionClearance($db,1),'changed evidence automatically revokes execution clearance');
$db->exec("UPDATE documents SET body='Source text unchanged' WHERE id=1");
ok(zmGovHasExecutionClearance($db,1),'restored identical evidence revalidates clearance');
$db->exec("DELETE FROM zm_project_links WHERE project_id=1 AND source='document' AND reference='1'");
ok(!zmGovHasExecutionClearance($db,1),'missing source link revokes execution clearance');
$db->exec("INSERT INTO zm_project_links(project_id,source,reference,reason,created_by) VALUES(1,'document','1','Source link restored',1)");
ok(zmGovHasExecutionClearance($db,1),'source link restoration revalidates clearance');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_events WHERE action='approved'")===1,'approved decision event');
denied(fn()=>zmGovHandle($db,'project_approval_decide'),409,'already decided case cannot be approved again');
$ROLE='admin';$ACTOR=1;
$FORM=['project_id'=>'1','expected_state'=>'planned','next_state'=>'active','reason'=>'Internal approval reference case 1'];
zmPmHandle($db,'project_transition');
ok(one($db,'SELECT state FROM projects WHERE id=1')==='active','governed active transition accepted');
$FORM=['project_id'=>'2','expected_state'=>'paused','next_state'=>'active','reason'=>'Cannot activate unapproved'];
denied(fn()=>zmPmHandle($db,'project_transition'),409,'unapproved project transition blocked');
$FORM=['project_id'=>'1','kind'=>'documentation','subject'=>'Review source memo','justification'=>'Administrative document quality review','evidence_doc_id'=>'1'];
zmGovHandle($db,'project_approval_submit');
ok((int)one($db,'SELECT COUNT(*) FROM zm_project_approval_cases')===2,'second kind allowed independently');
$FORM=['case_id'=>'2','decision'=>'approved','decision_note'=>'Administrative document check performed'];
zmGovHandle($db,'project_approval_decide');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_cases WHERE kind='documentation' AND status='approved'")===1,'ordinary administrative decision logged');
$FORM=['project_id'=>'1','kind'=>'documentation','subject'=>'Edited case','justification'=>'Request to replace evidence','evidence_doc_id'=>'1'];
zmGovHandle($db,'project_approval_submit');
$db->exec("UPDATE documents SET body='Modified source text' WHERE id=1");
$FORM=['case_id'=>'3','decision'=>'approved','decision_note'=>'Must reject changed evidence'];
$ACTOR=2;
denied(fn()=>zmGovHandle($db,'project_approval_decide'),409,'tampered evidence blocks approval');
$db->exec("UPDATE documents SET body='Source text unchanged' WHERE id=1");
zmGovHandle($db,'project_approval_decide');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_cases WHERE status='approved'")===3,'approved cases persist across kinds');
$ACTOR=1;
$FORM=['project_id'=>'1','kind'=>'documentation','subject'=>'Withdrawn review','justification'=>'No longer needed','evidence_doc_id'=>'1'];
zmGovHandle($db,'project_approval_submit');
$FORM=['case_id'=>'4','withdraw_note'=>'Superseded by newer approved evidence'];
zmGovHandle($db,'project_approval_withdraw');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_events WHERE action='withdrawn'")===1,'withdrawal event retained');
denied(fn()=>zmGovHandle($db,'project_approval_withdraw'),409,'cannot withdraw twice');
$FORM=['project_id'=>'1','kind'=>'documentation','subject'=>'Manager review','justification'=>'Independent administrative check','evidence_doc_id'=>'1'];
$ROLE='manager';$ACTOR=3;
zmGovHandle($db,'project_approval_submit');
$ACTOR=1;$ROLE='admin';
$FORM=['case_id'=>'5','withdraw_note'=>'Admin cancels obsolete request'];
zmGovHandle($db,'project_approval_withdraw');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_cases WHERE status='withdrawn'")===2,'owner can withdraw other pending request');
$_GET['project_id']='1';ob_start();zmGovRender($db);$html=ob_get_clean();
ok(str_contains($html,'گردش مستند تصمیم‌های پروژه'),'governance dossier renders');
ok(str_contains($html,'تاریخچه تصمیم‌های پرونده'),'history renders');
ok(str_contains($html,'مجوز داخلی شروع اجرا'),'clearance shown');
$ROLE='viewer';$ACTOR=4;
ob_start();zmGovRender($db);$viewerHtml=ob_get_clean();
ok(!str_contains($viewerHtml,'name="decision"'),'viewer cannot see final decision form');
ok(!str_contains($viewerHtml,'name="kind"'),'viewer cannot submit approval request');
$ROLE='admin';$ACTOR=1;
$ROLE='manager';$ACTOR=3;
$FORM=['project_id'=>'1','kind'=>'documentation','subject'=>'Reject outdated document','justification'=>'Requires independent editorial correction','evidence_doc_id'=>'1'];
zmGovHandle($db,'project_approval_submit');
$db->exec("UPDATE documents SET body='Altered after filing' WHERE id=1");
$ROLE='admin';$ACTOR=2;
$FORM=['case_id'=>'6','decision'=>'approved','decision_note'=>'Should not approve mutated doc'];
denied(fn()=>zmGovHandle($db,'project_approval_decide'),409,'tampered document cannot be approved');
$FORM=['case_id'=>'6','decision'=>'rejected','decision_note'=>'Evidence no longer matches attached submitted document'];
zmGovHandle($db,'project_approval_decide');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_cases WHERE id=6 AND status='rejected'")===1,'tampered request can be rejected with logged decision');
ok((int)one($db,"SELECT COUNT(*) FROM zm_project_approval_events WHERE case_id=6 AND action='rejected'")===1,'rejection evidence event appended');
$db->exec("UPDATE documents SET body='Source text unchanged' WHERE id=1");
$ROLE='admin';$ACTOR=1;
ok($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','database integrity');
ok($db->query('PRAGMA foreign_key_check')->fetchAll()===[],'reference integrity');
echo "TOTAL_PASSED=$pass\n";

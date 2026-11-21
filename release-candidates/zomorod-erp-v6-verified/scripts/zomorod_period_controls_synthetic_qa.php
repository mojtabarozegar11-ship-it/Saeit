<?php
declare(strict_types=1);
error_reporting(E_ALL);
function bail(string $message,int $code=422):never {throw new RuntimeException($message,$code);}
function mbSafeLen(string $s):int {return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}
function authorize(string $scope):void {if($scope!=='account')bail('permission denied',403);}
function actor():int {return 2;}
function role():string {return 'admin';}
function esc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function q(PDO $db,string $sql,array $args=[]):array{$q=$db->prepare($sql);$q->execute($args);return $q->fetchAll(PDO::FETCH_ASSOC);}
function formBegin(string $action):void{echo '<form data-action="'.esc($action).'">';}
function expect(bool $ok,string $test):void{if(!$ok)throw new RuntimeException('PERIOD_REGRESSION='.$test);}
function rejected(callable $callback,int $code,string $case):void {
    try{$callback();}catch(RuntimeException $e){expect($e->getCode()===$code,$case.'_code');return;}
    throw new RuntimeException('PERIOD_REGRESSION='.$case.'_accepted');
}
require __DIR__.'/../content/zomorod-business/period_controls.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$db->exec('PRAGMA foreign_keys=ON');
$db->exec('CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT)');
$db->exec("INSERT INTO users(id,role) VALUES(1,'accountant'),(2,'admin')");
$db->exec('CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT,doc_date TEXT)');
$db->exec('CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER REFERENCES journal_entries(id),account_id INTEGER,currency TEXT,debit INTEGER,credit INTEGER)');
$db->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_date TEXT,invoice_no TEXT,posted_entry INTEGER)');
$db->exec('CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id),paid_on TEXT,amount INTEGER,entry_id INTEGER)');
zmPeriodSchema($db);
$db->exec("INSERT INTO journal_entries VALUES(1,'TEST-1','2026-10-03')");
$db->exec("INSERT INTO journal_lines VALUES(1,1,10,'IRR',10000,0),(2,1,20,'IRR',0,9900)");
rejected(fn()=>zmPeriodAction($db,'period_freeze','2026-10','Request with imbalance',1,'accountant'),409,'refuse_imbalanced_close');
expect((int)$db->query('SELECT COUNT(*) FROM zm_accounting_periods')->fetchColumn()===0,'failed_request_not_saved');
$db->exec('UPDATE journal_lines SET credit=10000 WHERE id=2');
zmPeriodGuard($db,'2026-10-12');
zmPeriodAction($db,'period_freeze','2026-10','Checked synthetic journal balance',1,'accountant');
expect($db->query("SELECT state FROM zm_accounting_periods WHERE period_key='2026-10'")->fetchColumn()==='pending','pending_freeze');
rejected(fn()=>zmPeriodGuard($db,'2026-10-04'),409,'pending_month_blocked');
zmPeriodGuard($db,'2026-11-04');
rejected(fn()=>zmPeriodAction($db,'period_close','2026-10','Same actor',1,'admin'),403,'self_approval_denied');
rejected(fn()=>zmPeriodAction($db,'period_close','2026-10','Wrong role',2,'accountant'),403,'reviewer_must_be_admin');
$ledgerDenied=false;
try{$db->exec('UPDATE journal_lines SET credit=9998 WHERE id=2');}catch(PDOException $e){$ledgerDenied=true;}
expect($ledgerDenied,'frozen_period_refuses_mutation');
$db->exec("INSERT INTO invoices(id,invoice_date,invoice_no) VALUES(1,'2026-09-03','LEGACY-INV')");
$invoiceDenied=false;
try{$db->exec("INSERT INTO invoices(id,invoice_date,invoice_no) VALUES(2,'2026-10-11','BACKDATED')");}catch(PDOException $e){$invoiceDenied=true;}
expect($invoiceDenied,'frozen_invoice_blocked');
$db->exec("INSERT INTO invoice_payments(id,invoice_id,paid_on,amount) VALUES(1,1,'2026-11-02',100)");
$paymentDenied=false;
try{$db->exec("INSERT INTO invoice_payments(id,invoice_id,paid_on,amount) VALUES(2,1,'2026-10-11',100)");}catch(PDOException $e){$paymentDenied=true;}
expect($paymentDenied,'frozen_payment_blocked');
zmPeriodAction($db,'period_close','2026-10','Manually reviewed evidence for synthetic data',2,'admin');
expect($db->query("SELECT approved_by FROM zm_accounting_periods WHERE period_key='2026-10'")->fetchColumn()==2,'second_admin_approval');
rejected(fn()=>zmPeriodGuard($db,'2026-10-31'),409,'closed_period_locked');
rejected(fn()=>zmPeriodAction($db,'period_freeze','2026-10','Duplicate freeze',1,'accountant'),409,'duplicate_freeze');
rejected(fn()=>zmPeriodAction($db,'period_close','2026-10','Duplicate close',2,'admin'),409,'duplicate_approval');
expect((int)$db->query('SELECT COUNT(*) FROM zm_period_events')->fetchColumn()===2,'event_chain');
$immutable=false;try{$db->exec('DELETE FROM zm_period_events');}catch(PDOException $e){$immutable=true;}
expect($immutable,'append_only_events');
$permanent=false;try{$db->exec('DELETE FROM zm_accounting_periods');}catch(PDOException $e){$permanent=true;}
expect($permanent,'no_delete_closed_periods');
ob_start();zmPeriodRender($db);$html=(string)ob_get_clean();
expect(str_contains($html,'2026-10')&&str_contains($html,'بستن دوره'),'render_period_controls');
expect($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','db_integrity');
echo "ZM_PERIOD_CLOSURE_SYNTHETIC_QA=PASS\n";
echo "CURRENCY_BALANCE=PASS TWO_PERSON_APPROVAL=PASS DB_FREEZE=PASS\n";
echo "IMMUTABLE_EVENTS=PASS CLOSED_POSTING_GUARD=PASS COMPANY_DB=NOT_USED\n";

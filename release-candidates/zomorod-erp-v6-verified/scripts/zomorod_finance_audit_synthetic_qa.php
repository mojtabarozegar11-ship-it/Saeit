<?php
declare(strict_types=1);
error_reporting(E_ALL);
function authorize(string $scope):void{if($scope!=='account'||($GLOBALS['role']??'accountant')==='viewer')throw new RuntimeException('unauthorized',403);}
function q(PDO $db,string $s,array $args=[]):array{$q=$db->prepare($s);$q->execute($args);return $q->fetchAll(PDO::FETCH_ASSOC);}
function esc(mixed $s):string{return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function money(int $n):string{return number_format($n/100,2,'.',',');}
function test(bool $x,string $case):void{if(!$x)throw new RuntimeException('FINANCE_QA_FAILED='.$case);}
require __DIR__.'/../content/zomorod-business/finance_audit.php';
$db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$db->exec('PRAGMA foreign_keys=ON');
$db->exec('CREATE TABLE journal_entries(id INTEGER PRIMARY KEY,doc_no TEXT)');
$db->exec('CREATE TABLE journal_lines(id INTEGER PRIMARY KEY,entry_id INTEGER NOT NULL REFERENCES journal_entries(id),currency TEXT,debit INTEGER,credit INTEGER)');
$db->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY, amount INTEGER NOT NULL,posted_entry INTEGER)');
$db->exec('CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER REFERENCES invoices(id),amount INTEGER NOT NULL,entry_id INTEGER)');
$db->exec('CREATE TABLE inventory(id INTEGER PRIMARY KEY)');
$db->exec('CREATE TABLE inventory_movements(id INTEGER PRIMARY KEY,inventory_id INTEGER REFERENCES inventory(id),qty INTEGER,movement_date TEXT)');
$clean=zmFinanceAudit($db);
test($clean['result']==='CLEAR_ON_CHECKED_INVARIANTS','empty_healthy');
$db->exec("INSERT INTO journal_entries VALUES(1,'BALANCED')");
$db->exec("INSERT INTO journal_lines VALUES(1,1,'IRR',10000,0),(2,1,'IRR',0,10000)");
$db->exec('INSERT INTO invoices VALUES(1,10000,1)');
$db->exec('INSERT INTO invoice_payments VALUES(1,1,5000,2)');
$db->exec('INSERT INTO inventory VALUES(1)');
$db->exec("INSERT INTO inventory_movements VALUES(1,1,2,'2026-10-01')");
$pass=zmFinanceAudit($db);
test($pass['result']==='CLEAR_ON_CHECKED_INVARIANTS'&&array_sum($pass['checks'])===0,'balanced_ledger');
$db->exec("INSERT INTO journal_entries VALUES(2,'UNBALANCED')");
$db->exec("INSERT INTO journal_lines VALUES(3,2,'USD',500,0),(4,2,'USD',0,200)");
$db->exec('INSERT INTO invoice_payments VALUES(2,1,6000,3)');
$db->exec("INSERT INTO inventory_movements VALUES(2,1,-5,'2026-10-02')");
$bad=zmFinanceAudit($db);
test($bad['result']==='REQUIRES_INVESTIGATION','find_anomalies');
test($bad['checks']['entry_currency_balance']===1,'unbalanced_doc');
test($bad['checks']['currency_balance']===1,'unbalanced_currency');
test($bad['checks']['invoice_overpayment']===1,'overpaid_invoice');
test($bad['checks']['negative_stock']===1,'negative_inventory');
test($bad['checks']['foreign_keys']===0,'fk_preserved');
test($bad['checks']['historical_negative_stock']===1,'historical_negative_stock');
$db->exec('INSERT INTO invoices VALUES(2,10000,1)');
$reused=zmFinanceAudit($db);
test($reused['checks']['posting_reuse']===1,'duplicate_posting_link_detected');
// History can be negative even when final stock is positive.
$db->exec('INSERT INTO inventory VALUES(2)');
$db->exec("INSERT INTO inventory_movements VALUES(3,2,-4,'2026-10-01'),(4,2,7,'2026-10-02')");
$historical=zmFinanceAudit($db);
test($historical['checks']['historical_negative_stock']===2,'hidden_negative_history_detected');
$before=$db->query('SELECT COUNT(*) FROM journal_lines')->fetchColumn();
ob_start();zmFinanceAuditRender($db);$html=(string)ob_get_clean();
test(str_contains($html,'ممیزی مستقل')&&str_contains($html,'REQUIRES_INVESTIGATION'),'render_alert');
test($db->query('SELECT COUNT(*) FROM journal_lines')->fetchColumn()===$before,'read_only');
$GLOBALS['role']='viewer';
$denied=false;try{zmFinanceAuditRender($db);}catch(RuntimeException $e){$denied=$e->getCode()===403;}
test($denied,'viewer_forbidden');
echo "ZOMOROD_FINANCE_AUDIT_OFFLINE_QA=PASS\n";
echo "BALANCE_FX_OVERPAYMENT_NEGATIVE_STOCK=PASS READ_ONLY_RBAC=PASS\n";

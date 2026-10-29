<?php
declare(strict_types=1);
/** Purely synthetic test of Zomorod private command-control module. */
error_reporting(E_ALL);
function actor(): int { return 7; }
function role(): string { return $GLOBALS['synthetic_role'] ?? 'admin'; }
function bail(string $msg,int $code=422): never { throw new RuntimeException($msg,$code); }
function req(string $key,string $default=''): string { return (string)($GLOBALS['synthetic_post'][$key]??$default); }
function mbSafeLen(string $text): int { return function_exists('mb_strlen')?mb_strlen($text,'UTF-8'):strlen($text); }
function money(int $value): string { return number_format($value/100,2,'.',','); }
function esc(mixed $s): string { return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function formBegin(string $action): void { echo '<form method="post"><input name="action" value="'.esc($action).'">'; }
function q(PDO $db,string $sql,array $params=[]): array {
    $statement=$db->prepare($sql);$statement->execute($params);return $statement->fetchAll(PDO::FETCH_ASSOC);
}
function must(bool $condition,string $message): void { if(!$condition)throw new RuntimeException('TEST_FAILURE='.$message); }
require __DIR__.'/../content/zomorod-business/command_center.php';
$private=sys_get_temp_dir().'/zm-cc-test-'.bin2hex(random_bytes(10));
mkdir($private,0700);
try {
    $control=zmCcDb($private);
    must((fileperms($private.'/command-center.sqlite3')&0777)===0600,'private_storage_mode');
    $db=new PDO('sqlite::memory:',null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
    $db->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY,invoice_no TEXT,kind TEXT,currency TEXT,due_date TEXT,amount INTEGER)');
    $db->exec('CREATE TABLE invoice_payments(id INTEGER PRIMARY KEY,invoice_id INTEGER,amount INTEGER)');
    $db->exec('CREATE TABLE inventory(id INTEGER PRIMARY KEY,sku TEXT,name TEXT,reorder_level INTEGER)');
    $db->exec('CREATE TABLE inventory_movements(id INTEGER PRIMARY KEY,inventory_id INTEGER,qty INTEGER)');
    $due=(new DateTimeImmutable('yesterday',new DateTimeZone('UTC')))->format('Y-m-d');
    $s=$db->prepare('INSERT INTO invoices VALUES(1,?,?,?,?,?)');
    $s->execute(['INV-SYNTH-1','sale','IRR',$due,100000]);
    $db->exec('INSERT INTO invoice_payments VALUES(1,1,20000)');
    $db->exec("INSERT INTO inventory VALUES(1,'SKU-SYNTH','Synthetic product',5)");
    $key='0123456789abcdef0123456789abcdef';
    must(zmCcCreate($control,$key,null,'projects','Review synthetic project','Acceptance criteria','high',7),'create_task');
    must(!zmCcCreate($control,$key,null,'projects','Review synthetic project','Acceptance criteria','high',7),'deduplicate_manual');
    must((int)$control->query('SELECT COUNT(*) FROM tasks')->fetchColumn()===1,'single_manual_task');
    $result=zmCcScan($db,$control,7);
    must($result['created']===2 && $result['inspected']===2,'first_scanner');
    $again=zmCcScan($db,$control,7);
    must($again['created']===0 && $again['inspected']===2,'scan_deduplication');
    must((int)$control->query('SELECT COUNT(*) FROM tasks')->fetchColumn()===3,'total_tasks');
    must((int)$db->query('SELECT amount FROM invoices WHERE id=1')->fetchColumn()===100000,'company_invoice_read_only');
    must((int)$db->query('SELECT COUNT(*) FROM inventory_movements')->fetchColumn()===0,'company_stock_read_only');
    zmCcTransition($control,1,'in_progress','Started',7);
    zmCcTransition($control,1,'done','Evidence checked',7);
    must($control->query('SELECT state FROM tasks WHERE id=1')->fetchColumn()==='done','task_completed');
    $invalid=false;
    try { zmCcTransition($control,1,'in_progress','reopen',7); } catch(RuntimeException $e) { $invalid=true; }
    must($invalid,'forbid_reopening_terminal_task');
    must((int)$control->query('SELECT COUNT(*) FROM task_events WHERE task_id=1')->fetchColumn()===3,'event_chain');
    $GLOBALS['synthetic_role']='viewer';
    $denied=false;
    try { zmCcRequireAdmin(); } catch(RuntimeException $e) { $denied=$e->getCode()===403; }
    must($denied,'viewer_forbidden');
    $GLOBALS['synthetic_role']='admin';
    $xss='Summary <script>alert(1)</script>';
    must(zmCcCreate($control,'abcdef0123456789abcdef0123456789',null,'company',$xss,'No external action','normal',7),'escape_seed');
    ob_start();zmCcRender($control);$html=(string)ob_get_clean();
    must(str_contains($html,'&lt;script&gt;'),'html_escape');
    must(!str_contains($html,'<script>'),'no_inline_script');
    must(str_contains($html,'صف وظایف ماندگار'),'command_center_visible');
    echo "COMMAND_CENTER_SYNTHETIC_QA=PASS\n";
    echo "TASK_DURABILITY=PASS TASK_DEDUPLICATION=PASS AUTHORIZATION=PASS\n";
    echo "MANUAL_SCAN_READONLY=PASS EVENT_LOG=PASS HTML_ESCAPING=PASS\n";
    echo "EXTERNAL_EXECUTION=DISABLED RECURRING_SCHEDULE=NOT_CREATED\n";
} finally {
    $control=null;
    foreach(glob($private.'/*')?:[] as $file) if(is_file($file))unlink($file);
    rmdir($private);
}

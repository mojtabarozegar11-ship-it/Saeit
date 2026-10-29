<?php
declare(strict_types=1);
/** Synthetic-only SQL-backed payroll QA. Never opens live personnel/financial records. */
error_reporting(E_ALL);
function mbSafeLen(string $s):int{return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}
function bail(string $message,int $code=422):never{throw new RuntimeException($message,$code);}
function check(bool $ok,string $name):void{if(!$ok)throw new RuntimeException('QA_FAILED='.$name);}
function blocked(callable $f,int $code,string $name):void{
    try{$f();}catch(RuntimeException $e){check($e->getCode()===$code,$name.'_code');return;}
    throw new RuntimeException('QA_FAILED='.$name.'_accepted');
}
require __DIR__.'/../content/zomorod-business/payroll_control.php';
$dir=sys_get_temp_dir().'/zm-payroll-'.bin2hex(random_bytes(12));mkdir($dir,0700);
try{
    $db=zmPayrollDb($dir);
    $key='dddddddddddddddddddddddddddddddd';
    $lines=[
        ['employee_ref'=>'EMP002','base'=>150000,'addition'=>20000,'deduction'=>30000],
        ['employee_ref'=>'EMP001','base'=>100000,'addition'=>5000,'deduction'=>10000],
    ];
    [$id,$created]=zmPayrollCreate($db,$key,'2026-10','IRR',$lines,51);
    check($created&&$id===1,'created');
    check((int)$db->query('SELECT gross_total FROM payroll_periods')->fetchColumn()===275000,'gross_minor');
    check((int)$db->query('SELECT deduction_total FROM payroll_periods')->fetchColumn()===40000,'deductions');
    check((int)$db->query('SELECT net_total FROM payroll_periods')->fetchColumn()===235000,'net_minor');
    check(count(zmPayrollAudit($db))===0,'totals_balanced');
    check((fileperms($dir.'/payroll-control.sqlite3')&0777)===0600,'private_permissions');
    [$again,$new]=zmPayrollCreate($db,$key,'2026-10','IRR',array_reverse($lines),51);
    check($again===1&&!$new,'idempotency_sorted_lines');
    blocked(fn()=>zmPayrollCreate($db,$key,'2026-10','IRR',[
        ['employee_ref'=>'EMP001','base'=>1,'addition'=>0,'deduction'=>0]
    ],51),409,'changed_same_key');
    blocked(fn()=>zmPayrollCreate($db,'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-10','IRR',$lines,51),409,'unique_period');
    blocked(fn()=>zmPayrollCreate($db,'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-11','IRR',[
        ['employee_ref'=>'EMP999','base'=>100,'addition'=>0,'deduction'=>101]
    ],51),422,'excess_deduction');
    blocked(fn()=>zmPayrollCreate($db,'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-11','IRR',[
        ['employee_ref'=>'EMP999','base'=>100,'addition'=>0,'deduction'=>0],
        ['employee_ref'=>'EMP999','base'=>50,'addition'=>0,'deduction'=>0],
    ],51),422,'duplicate_employee');
    blocked(fn()=>zmPayrollCreate($db,'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-13','IRR',$lines,51),422,'invalid_month');
    zmPayrollDecision($db,1,'submit',51,'accountant','مستندات آزمون آماده');
    blocked(fn()=>zmPayrollDecision($db,1,'approve',51,'admin','Self approval'),403,'self_approve');
    blocked(fn()=>zmPayrollDecision($db,1,'approve',88,'accountant','Not authorized'),403,'non_admin_approval');
    zmPayrollDecision($db,1,'approve',88,'admin','Two-person reviewed synthetic report');
    check($db->query('SELECT state FROM payroll_periods')->fetchColumn()==='approved','independent_approval');
    blocked(fn()=>zmPayrollDecision($db,1,'approve',88,'admin','Double approval'),403,'no_repeat_approval');
    blocked(fn()=>zmPayrollDecision($db,1,'cancel',51,'accountant','Cancel approved'),403,'approved_immutable');
    check((int)$db->query('SELECT COUNT(*) FROM payroll_events')->fetchColumn()===3,'audit_events');
    try{$db->exec("UPDATE payroll_lines SET net_minor=0 WHERE employee_ref='EMP001'");check(false,'line_mutation_denied');}
    catch(PDOException $e){check(true,'line_mutation_denied');}
    try{$db->exec('DELETE FROM payroll_events');check(false,'audit_delete_denied');}
    catch(PDOException $e){check(true,'audit_delete_denied');}
    try{$db->exec("UPDATE payroll_periods SET net_total=1 WHERE id=1");check(false,'approved_total_immutable');}
    catch(PDOException $e){check(true,'approved_total_immutable');}
    check((int)$db->query('SELECT COUNT(*) FROM payroll_lines')->fetchColumn()===2,'line_count');
    check($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','integrity');
    $db=null;$db=zmPayrollDb($dir);
    check((int)$db->query('SELECT COUNT(*) FROM payroll_events')->fetchColumn()===3,'durability');
    echo "PAYROLL_OFFLINE_PDO_SQLITE_QA=PASS\n";
    echo "ARITHMETIC=PASS DEDUPE=PASS TWO_PERSON_CONTROL=PASS\n";
    echo "IMMUTABLE_AUDIT=PASS PRIVATE_STORAGE=PASS PERSISTENCE=PASS\n";
    echo "BANK_TRANSFERS=NONE TAX_FILINGS=NONE LIVE_EMPLOYEE_DATA=NONE\n";
} finally {
    $db=null;
    foreach(glob($dir.'/*')?:[] as $f)if(is_file($f))unlink($f);
    rmdir($dir);
}

<?php
declare(strict_types=1);
error_reporting(E_ALL);
function actor():int{return $GLOBALS['actor']??11;}
function role():string{return $GLOBALS['role']??'manager';}
function bail(string $msg,int $code=422):never{throw new RuntimeException($msg,$code);}
function req(string $key,string $default=''):string{return (string)($GLOBALS['post'][$key]??$default);}
function authorize(string $a):void{if($a==='view'&&!in_array(role(),['admin','manager','accountant','viewer'],true))bail('not allowed',403);}
function mbSafeLen(string $s):int{return function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s);}
function esc(mixed $v):string{return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function q(PDO $db,string $sql,array $params=[]):array{$s=$db->prepare($sql);$s->execute($params);return $s->fetchAll(PDO::FETCH_ASSOC);}
function formBegin(string $action):void{echo '<form name="'.esc($action).'">';}
function assertTrue(bool $x,string $m):void{if(!$x)throw new RuntimeException('INDUSTRY_TEST_FAILED='.$m);}
function rejects(callable $fn,int $expected,string $name):void{
    try{$fn();}catch(RuntimeException $e){assertTrue($e->getCode()===$expected,$name.'_code');return;}
    throw new RuntimeException('INDUSTRY_TEST_FAILED='.$name.'_not_rejected');
}
require __DIR__.'/../content/zomorod-business/industry_operations.php';
$private=sys_get_temp_dir().'/zm-industry-'.bin2hex(random_bytes(10));
mkdir($private,0700);
try{
    $db=zmIndustryDb($private);
    assertTrue((fileperms($private.'/industry-operations.sqlite3')&0777)===0600,'sqlite_file_private');
    [$plot,$made]=zmIndustryCreate($db,str_repeat('a',32),'plot','PL-1','قطعه آزمایشی','فقط داده مصنوعی',100,'ha',null,11);
    assertTrue($plot===1&&$made,'plot_created');
    [$same,$madeAgain]=zmIndustryCreate($db,str_repeat('a',32),'plot','PL-1','قطعه آزمایشی','فقط داده مصنوعی',100,'ha',null,11);
    assertTrue($same===$plot&&!$madeAgain,'idempotent_repeat');
    rejects(fn()=>zmIndustryCreate($db,str_repeat('a',32),'plot','PL-2','تغییر','داده',100,'ha',null,11),409,'replay_changed');
    rejects(fn()=>zmIndustryCreate($db,str_repeat('b',32),'crop','C-1','کشت','داده',12,'kg',null,11),422,'crop_needs_plot');
    [$crop]=zmIndustryCreate($db,str_repeat('b',32),'crop','C-1','کشت آزمایشی','بذر آزمایش مصنوعی',12,'kg',$plot,11);
    zmIndustryAdvance($db,$plot,'active','آماده کشت',11,'manager');
    zmIndustryAdvance($db,$crop,'growing','شروع کشت',11,'manager');
    rejects(fn()=>zmIndustryAdvance($db,$plot,'retired','در حال کشت',11,'manager'),409,'cannot_retire_active_plot');
    zmIndustryAdvance($db,$crop,'harvested','ثبت آزمایشی برداشت',11,'manager');
    rejects(fn()=>zmIndustryAdvance($db,$crop,'growing','بازگشت غیرمجاز',11,'manager'),409,'terminal_crop');
    [$sample]=zmIndustryCreate($db,str_repeat('c',32),'lab','LAB-1','نمونه آزمایشگاهی','نتیجه نیازمند بازبینی',1,'sample',null,11);
    zmIndustryAdvance($db,$sample,'testing','آزمایش شروع شد',11,'manager');
    zmIndustryAdvance($db,$sample,'review_required','مدرک بررسی لازم است',11,'manager');
    rejects(fn()=>zmIndustryAdvance($db,$sample,'verified','خودتأییدی ممنوع',11,'admin','https://example.org/evidence'),403,'self_review_blocked');
    rejects(fn()=>zmIndustryAdvance($db,$sample,'verified','بدون مدرک',12,'admin','http://example.org/evidence'),422,'insecure_evidence');
    zmIndustryAdvance($db,$sample,'verified','بازبینی داخلی مستقل',12,'admin','https://example.org/synthetic-evidence');
    assertTrue($db->query("SELECT reviewed_by FROM industry_items WHERE reference='LAB-1'")->fetchColumn()==12,'independent_review');
    [$batch]=zmIndustryCreate($db,str_repeat('d',32),'batch','B-1','بچ آزمایشی','تولید فرضی',20,'kg',null,11);
    zmIndustryAdvance($db,$batch,'producing','شروع تولید فرضی',11,'manager');
    rejects(fn()=>zmIndustryAdvance($db,$batch,'released','دور زدن کنترل کیفیت',12,'admin','https://example.org/evidence'),409,'batch_qa_gate');
    zmIndustryAdvance($db,$batch,'quality_hold','توقف تا بررسی',11,'manager');
    zmIndustryAdvance($db,$batch,'released','شواهد بررسی شد',12,'admin','https://example.org/batch-proof');
    [$asset]=zmIndustryCreate($db,str_repeat('e',32),'asset','AS-1','ماشین آزمایشی','ثبت وضعیت سرویس',1,'unit',null,11);
    zmIndustryAdvance($db,$asset,'maintenance','سرویس داخلی',11,'manager');
    zmIndustryAdvance($db,$asset,'in_service','بازگشت به سرویس',11,'manager');
    rejects(fn()=>zmIndustryAdvance($db,$asset,'retired','بازنشستگی بدون مجوز',13,'viewer'),403,'viewer_write_denied');
    $GLOBALS['role']='viewer';
    ob_start();zmIndustryRender($db);$page=(string)ob_get_clean();
    assertTrue(str_contains($page,'قطعات زمین')&&str_contains($page,'نمونه آزمایشگاه'),'read_only_view');
    assertTrue(!str_contains($page,'name="industry_create"'),'no_viewer_form');
    $GLOBALS['role']='admin';
    [$x]=zmIndustryCreate($db,str_repeat('f',32),'asset','XSS-1','<script>alert(1)</script>','نام آلوده فرضی',1,'unit',null,12);
    ob_start();zmIndustryRender($db);$html=(string)ob_get_clean();
    assertTrue(str_contains($html,'&lt;script&gt;')&&!str_contains($html,'<script>'),'xss_escaped');
    assertTrue($db->query('PRAGMA integrity_check')->fetchColumn()==='ok','sqlite_integrity');
    $n=(int)$db->query('SELECT COUNT(*) FROM industry_events')->fetchColumn();
    assertTrue($n>=14,'audit_trail');
    $db=null;$db=zmIndustryDb($private);
    assertTrue((int)$db->query('SELECT COUNT(*) FROM industry_items')->fetchColumn()===6,'persistence');
    echo "ZOMOROD_INDUSTRY_OFFLINE_QA=PASS\n";
    echo "CROP_LAB_BATCH_ASSET=PASS QUALITY_TWO_PERSON_REVIEW=PASS\n";
    echo "IDEMPOTENCY_PERMISSIONS_XSS_AUDIT=PASS REAL_COMPANY_DB=UNTOUCHED\n";
}finally{
    $db=null;
    foreach(glob($private.'/*')?:[] as $path){if(is_file($path))unlink($path);}
    rmdir($private);
}

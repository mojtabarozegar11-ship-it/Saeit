<?php
declare(strict_types=1);
/**
 * ZM project links + milestone calendar. Append-only audit in existing ledger DB;
 * reads satellite DBs using URI mode=ro, never changes payments, tasks, agents.
 */
function zmPiSchema(PDO $db):void {
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_links (
       id INTEGER PRIMARY KEY,
       project_id INTEGER NOT NULL REFERENCES projects(id),
       source TEXT NOT NULL CHECK(source IN ('document','invoice','journal','inventory','employee','task','workflow','industry','agent','report')),
       reference TEXT NOT NULL,
       reason TEXT NOT NULL,
       created_by INTEGER NOT NULL REFERENCES users(id),
       created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(project_id,source,reference)
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_project_links_by_project ON zm_project_links(project_id,id)');
    $db->exec("CREATE UNIQUE INDEX IF NOT EXISTS zm_project_financial_source_exclusive ON zm_project_links(source,reference) WHERE source IN ('invoice','journal')");
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_milestones (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        title TEXT NOT NULL,
        due_date TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'todo' CHECK(state IN ('todo','in_progress','blocked','done','cancelled')),
        created_by INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_pm_due ON zm_project_milestones(state,due_date,id)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_pm_project ON zm_project_milestones(project_id,id)');
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_milestone_events (
        id INTEGER PRIMARY KEY,
        milestone_id INTEGER NOT NULL REFERENCES zm_project_milestones(id),
        old_state TEXT NOT NULL,
        new_state TEXT NOT NULL,
        note TEXT NOT NULL,
        actor_id INTEGER NOT NULL REFERENCES users(id),
        occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_pm_events ON zm_project_milestone_events(milestone_id,id)');
}
function zmPiSources():array {
    return ['document'=>['اسناد اداری','documents','id',null],
            'invoice'=>['فاکتور','invoices','id',null],
            'journal'=>['سند روزنامه','journal_entries','id',null],
            'inventory'=>['کالا در انبار','inventory','id',null],
            'employee'=>['پرسنل','employees','id',null],
            'task'=>['وظیفه مرکز فرمان','tasks','id','command-center.sqlite3'],
            'workflow'=>['درخواست کارتابل','requests','id','company-workflow.sqlite3'],
            'industry'=>['عملیات سازمانی','industry_items','id','industry-operations.sqlite3'],
            'agent'=>['ایجنت سایت','agents','code','site_agents.sqlite3'],
            'report'=>['گزارش چرخه ChatGPT','reports','report_code','chatgpt_reports_archive.sqlite3']];
}
function zmPiSourceRole(string $source):array {
    return match($source) {
      'invoice','journal'=>['admin','accountant'],
      'task','agent','report'=>['admin'],
      'employee'=>['admin','manager'],
      default=>['admin','manager','accountant'],
    };
}
function zmPiRead(string $path):PDO {
    if(!is_file($path)||is_link($path)||!is_readable($path)||(fileperms($path)&0777)!==0600)
        throw new RuntimeException('Private integration database unavailable');
    $db=new PDO('sqlite:file:'.$path.'?mode=ro',null,null,
       [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>8]);
    $db->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=8000;');
    return $db;
}
function zmPiTarget(PDO $main,string $private,string $source,string $reference):array {
    $sources=zmPiSources();if(!isset($sources[$source]))bail('زیرسامانه انتخاب‌شده شناخته‌شده نیست.');
    [$label,$table,$col,$file]=$sources[$source];
    if(in_array($source,['agent','report'],true)){
        if(!preg_match($source==='agent'?'/^[a-zA-Z0-9_-]{2,60}$/D':'/^[0-9]{2}-[0-9]{4,8}$/D',$reference))
            bail('شناسه رکورد نامعتبر است.');
    } else {
        if(!preg_match('/^[1-9][0-9]{0,17}$/D',$reference)||
           filter_var($reference,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]])===false)
            bail('شناسه رکورد باید عددی و مثبت باشد.');
    }
    try {
        $conn=$file!==null?zmPiRead($private.'/'.$file):$main;
        $field=match($source){
           'document'=>'title', 'invoice'=>'invoice_no', 'journal'=>'doc_no',
           'inventory'=>'name','employee'=>'fullname','task'=>'title',
           'workflow'=>'title','industry'=>'title','agent'=>'title',
           'report'=>'report_code'
        };
        // Whitelist-only SQL identifiers; no dynamic identifiers from user.
        $stateCol=match($source){
            'task','workflow'=>'state','industry'=>'status','agent'=>'enabled',
            default=>null
        };
        $stmt=$conn->prepare('SELECT '.$field.' AS label'.($stateCol!==null?', '.$stateCol.' AS current_state':'').' FROM '.$table.' WHERE '.$col.'=? LIMIT 1');
        $stmt->execute([$reference]);$value=$stmt->fetch(PDO::FETCH_ASSOC);
        if($value===false)bail('رکورد مرجع در زیرسامانه یافت نشد؛ پیوند صوری مجاز نیست.',404);
        $current=(string)$value['label'];
        if($stateCol!==null)$current.=' | وضعیت منبع: '.(string)$value['current_state'];
        return [$label,$current];
    }catch(PDOException $e){error_log('ZM_PROJECT_REF_QUERY_ERROR '.get_class($e));bail('اعتبارسنجی مرجع در دسترس نیست.',503);}
}
function zmPiRequireActor(PDO $db,array $roles):void {
    $id=actor();
    if($id<1||!in_array(role(),$roles,true))bail('مجوز کافی برای پیوند پروژه وجود ندارد.',403);
    $st=$db->prepare('SELECT role,active FROM users WHERE id=?');$st->execute([$id]);$u=$st->fetch(PDO::FETCH_ASSOC);
    if(!$u||(int)$u['active']!==1||!in_array((string)$u['role'],$roles,true))bail('مجوز فعال نیست.',403);
}
function zmPiDate(string $v):string {
    $d=DateTimeImmutable::createFromFormat('!Y-m-d',$v);
    if(!$d||$d->format('Y-m-d')!==$v||$v<'2000-01-01'||$v>'2100-12-31')
        bail('تاریخ باید YYYY-MM-DD معتبر باشد.');
    return $v;
}
function zmPiHandle(PDO $db,string $private,string $action):void {
    zmPiSchema($db);
    $idText=req('project_id');
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$idText))bail('شناسه پروژه نامعتبر است.');
    $projectId=filter_var($idText,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($projectId===false)bail('شناسه پروژه نامعتبر است.');
    $db->exec('BEGIN IMMEDIATE');$locked=true;
    try {
        $project=$db->prepare('SELECT state,title FROM projects WHERE id=?');
        $project->execute([$projectId]);$item=$project->fetch(PDO::FETCH_ASSOC);
        if(!$item)bail('پروژه وجود ندارد.',404);
        $state=(string)$item['state'];
        $archived=zmPmIsArchiveOnly((string)$item['title']);
        $approved=zmPmIsApproved((string)$item['title']);
        if($action==='project_link'){
            $source=req('source');$reference=req('reference');$reason=zmPmClean(req('reason'),700);
            $roles=zmPiSourceRole($source);zmPiRequireActor($db,$roles);
            [$type,$name]=zmPiTarget($db,$private,$source,$reference);
            if($archived && !in_array($source,['document','report'],true))
                bail('پرونده ردشده فقط برای ارجاع تاریخی به سند یا گزارش بایگانی مجاز است.',409);
            if(!$approved && !in_array($source,['document','report','workflow'],true))
                bail('پرونده فاقد مصوبه قطعی فقط مرجع مکاتبات، گزارش و بررسی اداری می‌پذیرد.',409);
            $same=$db->prepare('SELECT id FROM zm_project_links WHERE project_id=? AND source=? AND reference=?');
            $same->execute([$projectId,$source,$reference]);
            if($same->fetchColumn()!==false)bail('این ارتباط قبلاً برای همین پروژه ثبت شده است.',409);
            if(in_array($source,['invoice','journal'],true)){
                $exclusive=$db->prepare('SELECT project_id FROM zm_project_links WHERE source=? AND reference=?');
                $exclusive->execute([$source,$reference]);
                if($exclusive->fetchColumn()!==false)
                    bail('انتساب مالی این سند به پروژه دیگری ثبت شده؛ برای جلوگیری از دوباره‌شماری مسدود شد.',409);
            }
            $ins=$db->prepare('INSERT INTO zm_project_links(project_id,source,reference,reason,created_by) VALUES(?,?,?,?,?)');
            $ins->execute([$projectId,$source,$reference,$reason,actor()]);
            audit($db,'link','project',$projectId);
        }elseif($action==='project_document'){
            zmPiRequireActor($db,['admin','manager','accountant']);
            if($archived||$state==='done')
                bail('برای پرونده ردشده یا مختومه سند اجرایی جدید مجاز نیست.',409);
            $title=zmPmClean(req('title'),160);
            $category=zmPmClean(req('category'),80);
            $body=zmPmClean(req('body'),12000);
            $statement=$db->prepare('INSERT INTO documents(title,category,body,created_by) VALUES(?,?,?,?)');
            $statement->execute([$title,$category,$body,actor()]);
            $docId=(int)$db->lastInsertId();
            $link=$db->prepare('INSERT INTO zm_project_links(project_id,source,reference,reason,created_by) VALUES(?,?,?,?,?)');
            $link->execute([$projectId,'document',(string)$docId,'سند اصلی این پرونده؛ ثبت همزمان با ارتباط پروژه',actor()]);
            audit($db,'create','document',$docId);
            audit($db,'link','project',$projectId);
        }elseif($action==='project_milestone'){
            zmPiRequireActor($db,['admin','manager']);
            if(!$approved||$state==='done')bail('برای پروژه فاقد مصوبه یا مختومه اقدام اجرایی جدید مجاز نیست.',409);
            $title=zmPmClean(req('title'),160);$due=zmPiDate(req('due_date'));
            $ins=$db->prepare('INSERT INTO zm_project_milestones(project_id,title,due_date,created_by) VALUES(?,?,?,?)');
            $ins->execute([$projectId,$title,$due,actor()]);
            $mid=(int)$db->lastInsertId();
            if(!function_exists('zmOpsAssignNew'))bail('دفتر ارجاع مسئول در دسترس نیست.',503);
            zmOpsSchema($db);
            zmOpsAssignNew($db,$mid,req('assigned_user_id'));
            $st=$db->prepare('INSERT INTO zm_project_milestone_events(milestone_id,old_state,new_state,note,actor_id) VALUES(?,?,?,?,?)');
            $st->execute([$mid,'','todo','ایجاد اقدام زمان‌دار بدون اجرای عملیات فیزیکی یا پرداخت.',actor()]);
            audit($db,'milestone','project',$projectId);
        }elseif($action==='project_milestone_state'){
            zmPiRequireActor($db,['admin','manager']);
            if(!$approved)bail('پرونده فاقد مصوبه قطعی نمی‌تواند وارد مسیر اجرای اقدام شود.',409);
            $midText=req('milestone_id');
            if(!preg_match('/^[1-9][0-9]{0,17}$/D',$midText))bail('شناسه اقدام معتبر نیست.');
            $mid=(int)$midText;
            $find=$db->prepare('SELECT state FROM zm_project_milestones WHERE id=? AND project_id=?');
            $find->execute([$mid,$projectId]);$old=$find->fetchColumn();
            if($old===false)bail('اقدام زمان‌دار در این پروژه یافت نشد.',404);
            $expected=req('expected_state');$next=req('next_state');
            $allowed=['todo'=>['in_progress','blocked','cancelled'],
                      'in_progress'=>['blocked','done','cancelled'],
                      'blocked'=>['in_progress','cancelled'],
                      'done'=>[], 'cancelled'=>[]];
            if($expected!==$old||!in_array($next,$allowed[$old]??[],true))
                bail('این تغییر وضعیت به‌دلیل تداخل یا ترتیب نامعتبر رد شد.',409);
            $note=zmPmClean(req('note'),900);
            $change=$db->prepare('UPDATE zm_project_milestones SET state=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND state=?');
            $change->execute([$next,$mid,$old]);
            if($change->rowCount()!==1)bail('تداخل همزمان؛ مجدد بارگذاری کنید.',409);
            $ins=$db->prepare('INSERT INTO zm_project_milestone_events(milestone_id,old_state,new_state,note,actor_id) VALUES(?,?,?,?,?)');
            $ins->execute([$mid,$old,$next,$note,actor()]);
            audit($db,'milestone-transition','project',$projectId);
        }else bail('عملیات ارتباطات پروژه شناخته نشده است.',403);
        $db->exec('COMMIT');$locked=false;
    }catch(Throwable $e){
        if($locked){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
        throw $e;
    }
}
function zmPiProjectOptions(PDO $db):string{
    $html='';
    foreach(q($db,'SELECT id,title FROM projects ORDER BY id DESC LIMIT 500') as $p)
       $html.='<option value="'.(int)$p['id'].'">#'.(int)$p['id'].' · '.esc($p['title']).'</option>';
    return $html;
}
function zmPiCalendar(PDO $db):void {
    authorize('view');zmPiSchema($db);
    $today=today();
    $rows=q($db,"SELECT m.id,m.project_id,p.title AS project_title,m.title,m.due_date,m.state
                 FROM zm_project_milestones m JOIN projects p ON p.id=m.project_id
                 WHERE m.state NOT IN ('done','cancelled')
                 ORDER BY m.due_date,m.id LIMIT 150");
    $overdue=0;foreach($rows as $r){if($r['due_date']<$today)$overdue++;}
    echo '<section><h2>تقویم عملیات و سررسیدهای پروژه‌ها</h2><p>امروز: '.esc($today).' · اقدام باز نمایش‌داده‌شده: '.count($rows).' · عقب‌افتاده در میان موارد نمایش‌داده‌شده: '.$overdue.'</p>';
    echo '<p class="muted">این تقویم وظایف داخلی را نمایش می‌دهد؛ شروع کار فیزیکی، تعهد مالی یا تأیید تکمیل را ایجاد نمی‌کند.</p>';
    echo '<div class="scroll"><table><tr><th>سررسید</th><th>پروژه</th><th>عنوان اقدام</th><th>وضعیت</th></tr>';
    $labels=['todo'=>'برنامه','in_progress'=>'در جریان','blocked'=>'مسدود','done'=>'انجام‌شده','cancelled'=>'لغوشده'];
    foreach($rows as $m){
      $mark=$m['due_date']<$today?' (معوق)':'';
      echo '<tr><td>'.esc($m['due_date'].$mark).'</td><td><a href="?page=project_links&project_id='.(int)$m['project_id'].'">'.esc($m['project_title']).'</a></td><td>'.esc($m['title']).'</td><td>'.esc($labels[$m['state']]??$m['state']).'</td></tr>';
    }
    if(!$rows)echo '<tr><td colspan="4">اقدام زمان‌دار ثبت‌شده‌ای وجود ندارد.</td></tr>';
    echo '</table></div></section>';
}
function zmPiAvailableReferences(PDO $db,string $private):void {
    echo '<details><summary>راهنمای شناسه‌های موجود برای اتصال (فقط رکوردهای واقعی)</summary>';
    echo '<p class="muted">لیست کوتاه از هر بخش. وجود رکورد به معنی تأیید محتوای آن نیست. شناسه را در فرم پیوند وارد کنید.</p>';
    echo '<div class="scroll"><table><tr><th>زیرسامانه</th><th>شناسه</th><th>عنوان موجود</th></tr>';
    $sources=zmPiSources();
    foreach($sources as $key=>$definition){
        if(!in_array(role(),zmPiSourceRole($key),true))continue;
        [$label,$table,$col,$file]=$definition;
        try{
            $sourceDb=$file!==null?zmPiRead($private.'/'.$file):$db;
            $titleColumn=match($key){
                'document'=>'title','invoice'=>'invoice_no','journal'=>'doc_no',
                'inventory'=>'name','employee'=>'fullname','task'=>'title',
                'workflow'=>'title','industry'=>'title','agent'=>'title',
                'report'=>'report_code'
            };
            $records=$sourceDb->query('SELECT '.$col.' AS reference,'.$titleColumn.' AS label FROM '.$table.' ORDER BY '.$col.' DESC LIMIT 12')->fetchAll();
            foreach($records as $record)
              echo '<tr><td>'.esc($label).'</td><td>'.esc($record['reference']).'</td><td>'.esc($record['label']).'</td></tr>';
        }catch(Throwable $ex){
            error_log('ZM_PROJECT_CATALOG_READ_ERROR '.get_class($ex));
        }
    }
    echo '</table></div></details>';
}
function zmPiRender(PDO $db,string $private):void {
    authorize('view');zmPiSchema($db);
    $projectText=(string)($_GET['project_id']??'');
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$projectText)) {
       echo '<section><h2>انتخاب پرونده برای اتصال سامانه‌ها</h2><p><a href="?page=projects">فهرست و وضعیت پروژه‌ها</a> · <a href="?page=project_calendar">تقویم پروژه‌ها</a></p>';
       echo '<form method="get"><input type="hidden" name="page" value="project_links"><label>پروژه</label><select name="project_id" required>'.zmPiProjectOptions($db).'</select><button>باز کردن پرونده یکپارچه</button></form></section>';
       return;
    }
    $pid=(int)$projectText;
    $stmt=$db->prepare('SELECT * FROM projects WHERE id=?');$stmt->execute([$pid]);$project=$stmt->fetch(PDO::FETCH_ASSOC);
    if(!$project)bail('پروژه یافت نشد.',404);
    $labels=['planned'=>'برنامه‌ریزی','active'=>'فعال ثبت‌شده','paused'=>'متوقف','done'=>'مختومه ثبت‌شده'];
    echo '<section><h2>پرونده یکپارچه پروژه #'.$pid.' — '.esc($project['title']).'</h2><p>مسئول: '.esc($project['owner']).' · وضعیت اداری: '.esc($labels[$project['state']]??$project['state']).' · بودجه پیشنهادی: '.money((int)$project['budget']).' ریال</p>';
    echo '<p class="muted">وجود پیوند با فاکتور یا سند مالی، تخصیص هزینه، پرداخت یا وصول را ثابت نمی‌کند. این صفحه عملیاتی فقط دفتر ارتباطات مستند است.</p>';
    echo '<p><a href="?page=projects">مدیریت پروژه‌ها</a> · <a href="?page=workflow_desk">کارتابل</a> · <a href="?page=project_calendar">تقویم پروژه‌ها</a> · <a href="?page=command_center">مرکز فرمان (مدیرکل)</a></p></section>';
    $archiveOnly=zmPmIsArchiveOnly((string)$project['title']);
    $approved=zmPmIsApproved((string)$project['title']);
    if(!$approved && !$archiveOnly)
        echo '<section><h2>پرونده فاقد مصوبه قطعی</h2><p>تا احراز مصوبه، فقط مکاتبات و بررسی اداری مجاز است؛ اجرای عملیات، گزارش پیشرفت فیزیکی یا انتساب مالی ممنوع است.</p></section>';
    if($archiveOnly)echo '<section><h2>پرونده ردشده — فقط بایگانی</h2><p>این پرونده برای سابقه تاریخی حفظ می‌شود و ایجاد اقدام، سند اجرایی یا ارتباط مالی جدید برای آن ممنوع است.</p></section>';
    $sourceNames=zmPiSources();
    $links=q($db,'SELECT l.*,u.username FROM zm_project_links l JOIN users u ON u.id=l.created_by WHERE l.project_id=? ORDER BY l.id DESC LIMIT 150',[$pid]);
    echo '<section><h2>پیوندهای مستند به زیرسامانه‌های شرکت</h2><div class="scroll"><table><tr><th>بخش</th><th>مرجع</th><th>عنوان مرجع</th><th>دلیل اتصال</th><th>ایجادکننده</th></tr>';
    foreach($links as $l){
       if(!in_array(role(),zmPiSourceRole((string)$l['source']),true))continue;
       try{[, $targetName]=zmPiTarget($db,$private,$l['source'],$l['reference']);$target='موجود: '.$targetName;}
       catch(Throwable $e){$target='مرجع قابل بازیابی نیست؛ بررسی لازم است';}
       echo '<tr><td>'.esc($sourceNames[$l['source']][0]).'</td><td>'.esc($l['reference']).'</td><td>'.esc($target).'</td><td>'.esc($l['reason']).'</td><td>'.esc($l['username']).'</td></tr>';
    }
    if(!$links)echo '<tr><td colspan="5">هنوز رکوردی به این پروژه متصل نشده است؛ انتساب خودکار از روی نام‌های مشابه ممنوع است.</td></tr>';
    echo '</table></div></section>';
    if(in_array(role(),['admin','manager','accountant'],true)){
      echo '<section><h2>اتصال یک رکورد واقعی به پروژه</h2><p class="muted">رکورد باید موجود باشد. اسناد اداری و اطلاعات غیرمالی می‌توانند با توضیح به چند پروژه مرتبط شوند؛ فاکتور و سند روزنامه فقط به یک پروژه منتسب می‌شوند و هیچ مبلغی خودکار تخصیص نمی‌یابد.</p>';
      formBegin('project_link');
      echo '<input type="hidden" name="project_id" value="'.$pid.'"><label>سامانه</label><select name="source">';
      foreach($sourceNames as $key=>$data)
         if(in_array(role(),zmPiSourceRole($key),true) &&
            ($approved || in_array($key,$archiveOnly?['document','report']:['document','report','workflow'],true)))
             echo '<option value="'.esc($key).'">'.esc($data[0]).'</option>';
      echo '</select><label>شناسه دقیق رکورد</label><input name="reference" required maxlength="60" placeholder="شماره ID؛ برای ایجنت کد و برای گزارش 05-0033">';
      echo '<label>دلیل ارتباط و سند</label><textarea name="reason" maxlength="700" required></textarea><button>ثبت پیوند قابل ممیزی</button></form>';
      zmPiAvailableReferences($db,$private);
      echo '</section>';
    }
    if(in_array(role(),['admin','manager','accountant'],true) && !$archiveOnly && $project['state']!=='done'){
       echo '<section><h2>ایجاد مکاتبه یا سند اداری مرتبط با همین پروژه</h2>';
       echo '<p class="muted">سند و پیوند آن در یک تراکنش واحد ثبت می‌شوند. هیچ قرارداد، تعهد مالی یا پیام خارجی ارسال نمی‌شود.</p>';
       formBegin('project_document');
       echo '<input type="hidden" name="project_id" value="'.$pid.'"><label>عنوان مکاتبه یا سند</label><input name="title" maxlength="160" required>';
       echo '<label>دسته سند</label><select name="category"><option value="مکاتبات">مکاتبات</option><option value="صورتجلسه">صورتجلسه</option><option value="پژوهش">پژوهش</option><option value="حقوقی و اداری">حقوقی و اداری</option></select>';
       echo '<label>متن سند</label><textarea name="body" maxlength="12000" required></textarea><button>ثبت سند و اتصال قطعی به پرونده</button></form></section>';
    }
    $milestones=q($db,'SELECT * FROM zm_project_milestones WHERE project_id=? ORDER BY due_date,id LIMIT 200',[$pid]);
    $states=['todo'=>'برنامه‌ریزی','in_progress'=>'در جریان','blocked'=>'مسدود','done'=>'تکمیل اداری','cancelled'=>'لغوشده'];
    $transitions=['todo'=>['in_progress','blocked','cancelled'],
                  'in_progress'=>['blocked','done','cancelled'],
                  'blocked'=>['in_progress','cancelled'],'done'=>[],'cancelled'=>[]];
    $canEdit=in_array(role(),['admin','manager'],true) && $approved;
    echo '<section><h2>وظایف زمان‌دار و نقاط عطف پروژه</h2><div class="scroll"><table><tr><th>سررسید</th><th>عنوان</th><th>وضعیت</th>'.($canEdit?'<th>تصمیم با دلیل</th>':'').'</tr>';
    foreach($milestones as $m){
      echo '<tr><td>'.esc($m['due_date']).'</td><td>'.esc($m['title']).'</td><td>'.esc($states[$m['state']]??$m['state']).'</td>';
      if($canEdit){
       echo '<td>';
       if($transitions[$m['state']]??[]){
        formBegin('project_milestone_state');
        echo '<input type="hidden" name="project_id" value="'.$pid.'"><input type="hidden" name="milestone_id" value="'.(int)$m['id'].'"><input type="hidden" name="expected_state" value="'.esc($m['state']).'">';
        echo '<select name="next_state">';
        foreach($transitions[$m['state']] as $target)echo '<option value="'.esc($target).'">'.esc($states[$target]).'</option>';
        echo '</select><input name="note" required maxlength="900" placeholder="دلیل و مدرک تصمیم"><button>ثبت تصمیم</button></form>';
       }else echo 'مختومه';
       echo '</td>';
      }
      echo '</tr>';
    }
    if(!$milestones)echo '<tr><td colspan="'.($canEdit?4:3).'">اقدام زمان‌داری ثبت نشده است.</td></tr>';
    echo '</table></div></section>';
    if(function_exists('zmOpsAssignmentSection'))
        zmOpsAssignmentSection($db,$pid,$canEdit && $project['state']!=='done');
    if(in_array(role(),['admin','accountant'],true))
        echo '<p><a href="?page=project_finance&amp;project_id='.$pid.'">گزارش اسناد مالی ثبت‌شده این پروژه</a></p>';
    if($canEdit && $project['state']!=='done'){
      echo '<section><h2>تعریف اقدام با سررسید</h2>';formBegin('project_milestone');
      echo '<input type="hidden" name="project_id" value="'.$pid.'"><label>عنوان اقدام</label><input name="title" required maxlength="160">';
      echo '<label>سررسید میلادی</label><input type="date" name="due_date" value="'.esc(today()).'" required>';
      echo '<label>کاربر مسئول در سامانه</label><select name="assigned_user_id" required>'.zmOpsUserOptions($db,actor()).'</select>';
      echo '<button>ثبت اقدام و ارجاع به مسئول واقعی</button></form></section>';
    }
    echo '<section><h2>تاریخچه تصمیم‌های زمان‌دار</h2><div class="scroll"><table><tr><th>اقدام</th><th>از</th><th>به</th><th>دلیل</th><th>ثبت‌کننده</th><th>زمان UTC</th></tr>';
    foreach(q($db,'SELECT e.*,m.title,u.username FROM zm_project_milestone_events e JOIN zm_project_milestones m ON e.milestone_id=m.id JOIN users u ON u.id=e.actor_id WHERE m.project_id=? ORDER BY e.id DESC LIMIT 80',[$pid]) as $e)
      echo '<tr><td>'.esc($e['title']).'</td><td>'.esc($e['old_state']).'</td><td>'.esc($e['new_state']).'</td><td>'.esc($e['note']).'</td><td>'.esc($e['username']).'</td><td>'.esc($e['occurred_at']).'</td></tr>';
    echo '</table></div></section>';
}

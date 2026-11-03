<?php
declare(strict_types=1);
/** Internal project governance. Decisions do not change finance, contracts or project states. */
function zmGovSchema(PDO $db):void {
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_approval_cases (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        kind TEXT NOT NULL CHECK(kind IN ('documentation','execution')),
        subject TEXT NOT NULL,
        justification TEXT NOT NULL,
        evidence_doc_id INTEGER NOT NULL REFERENCES documents(id),
        evidence_sha256 TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'submitted' CHECK(status IN ('submitted','approved','rejected','withdrawn')),
        requested_by INTEGER NOT NULL REFERENCES users(id),
        reviewed_by INTEGER REFERENCES users(id),
        decision_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_approval_by_project ON zm_project_approval_cases(project_id,id)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_approval_pending ON zm_project_approval_cases(status,kind,id)');
    $db->exec("CREATE UNIQUE INDEX IF NOT EXISTS zm_approval_one_pending ON zm_project_approval_cases(project_id,kind) WHERE status='submitted'");
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_approval_events (
        id INTEGER PRIMARY KEY,
        case_id INTEGER NOT NULL REFERENCES zm_project_approval_cases(id),
        action TEXT NOT NULL CHECK(action IN ('submitted','approved','rejected','withdrawn')),
        note TEXT NOT NULL,
        actor_id INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_approval_event_by_case ON zm_project_approval_events(case_id,id)');
}
function zmGovRealActor(PDO $db,array $allowed):void {
    $userId=actor();
    if($userId<1||!in_array(role(),$allowed,true))bail('مجوز اقدام در مصوبات پروژه وجود ندارد.',403);
    $q=$db->prepare('SELECT role,active FROM users WHERE id=?');
    $q->execute([$userId]);$u=$q->fetch(PDO::FETCH_ASSOC);
    if(!$u||(int)$u['active']!==1||!in_array((string)$u['role'],$allowed,true))bail('حساب مجاز و فعال نیست.',403);
}
function zmGovPositiveId(string $value):int {
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$value))bail('شناسه معتبر نیست.',422);
    $id=filter_var($value,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($id===false)bail('شناسه معتبر نیست.',422);
    return (int)$id;
}
function zmGovHasExecutionClearance(PDO $db,int $projectId):bool {
    zmGovSchema($db);
    // Fail closed if a previously approved document or its project link changed.
    $stmt=$db->prepare("SELECT c.evidence_sha256,d.title,d.body
       FROM zm_project_approval_cases c
       JOIN documents d ON d.id=c.evidence_doc_id
       JOIN users reviewer ON reviewer.id=c.reviewed_by
         AND reviewer.active=1 AND reviewer.role='admin'
       JOIN zm_project_links l ON l.project_id=c.project_id
         AND l.source='document' AND l.reference=CAST(c.evidence_doc_id AS TEXT)
       WHERE c.project_id=? AND c.kind='execution' AND c.status='approved'
         AND c.reviewed_by IS NOT NULL AND c.reviewed_by<>c.requested_by
       ORDER BY c.id DESC LIMIT 50");
    $stmt->execute([$projectId]);
    foreach($stmt->fetchAll(PDO::FETCH_ASSOC) as $r){
        $digest=hash('sha256',(string)$r['title']."\n".(string)$r['body']);
        if(hash_equals((string)$r['evidence_sha256'],$digest))return true;
    }
    return false;
}
function zmGovHandle(PDO $db,string $action):void {
    zmGovSchema($db);
    if($action==='project_approval_submit'){
        zmGovRealActor($db,['admin','manager']);
        $projectId=zmGovPositiveId(req('project_id'));
        $docId=zmGovPositiveId(req('evidence_doc_id'));
        $kind=req('kind');
        if(!in_array($kind,['documentation','execution'],true))bail('نوع بررسی پروژه نامعتبر است.',422);
        $subject=zmPmClean(req('subject'),160);
        $rationale=zmPmClean(req('justification'),1200);
        $db->exec('BEGIN IMMEDIATE');$inTransaction=true;
        try {
            zmGovRealActor($db,['admin','manager']);
            $stmt=$db->prepare('SELECT title,state FROM projects WHERE id=?');
            $stmt->execute([$projectId]);$project=$stmt->fetch(PDO::FETCH_ASSOC);
            if(!$project)bail('پروژه یافت نشد.',404);
            if(zmPmIsArchiveOnly((string)$project['title'])||$project['state']==='done')
                bail('پرونده ردشده یا مختومه درخواست تصویب جدید نمی‌پذیرد.',409);
            if($kind==='execution'&&!zmPmIsApproved((string)$project['title']))
                bail('درخواست اجازه اجرا صرفاً برای طرح دارای برچسب مصوب قابل ثبت است.',409);
            $linked=$db->prepare("SELECT COUNT(*) FROM zm_project_links WHERE project_id=? AND source='document' AND reference=?");
            $linked->execute([$projectId,(string)$docId]);
            if(!(int)$linked->fetchColumn())bail('ابتدا سند مدرک را به همین پرونده پروژه پیوند دهید.',409);
            $evidence=$db->prepare('SELECT title,body FROM documents WHERE id=?');
            $evidence->execute([$docId]);$doc=$evidence->fetch(PDO::FETCH_ASSOC);
            if(!$doc)bail('سند مدرک وجود ندارد.',404);
            $digest=hash('sha256',(string)$doc['title']."\n".(string)$doc['body']);
            $q=$db->prepare("SELECT id FROM zm_project_approval_cases WHERE project_id=? AND kind=? AND status='submitted'");
            $q->execute([$projectId,$kind]);
            if($q->fetchColumn()!==false)bail('برای این پروژه از این نوع یک درخواست باز وجود دارد.',409);
            $insert=$db->prepare("INSERT INTO zm_project_approval_cases
                (project_id,kind,subject,justification,evidence_doc_id,evidence_sha256,requested_by)
                VALUES (?,?,?,?,?,?,?)");
            $insert->execute([$projectId,$kind,$subject,$rationale,$docId,$digest,actor()]);
            $caseId=(int)$db->lastInsertId();
            $event=$db->prepare("INSERT INTO zm_project_approval_events(case_id,action,note,actor_id) VALUES(?,'submitted',?,?)");
            $event->execute([$caseId,'درخواست با سند متصل ثبت و جهت بررسی مدیر ارجاع شد.',actor()]);
            audit($db,'submit','project-approval',$caseId);
            $db->exec('COMMIT');$inTransaction=false;
        }catch(Throwable $e){
            if($inTransaction){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
            throw $e;
        }
        return;
    }
    if($action==='project_approval_decide'){
        zmGovRealActor($db,['admin']);
        $caseId=zmGovPositiveId(req('case_id'));
        $decision=req('decision');
        if(!in_array($decision,['approved','rejected'],true))bail('نتیجه بررسی معتبر نیست.',422);
        $note=zmPmClean(req('decision_note'),1200);
        $db->exec('BEGIN IMMEDIATE');$inTransaction=true;
        try {
            zmGovRealActor($db,['admin']);
            $q=$db->prepare('SELECT c.*,p.title AS project_title FROM zm_project_approval_cases c JOIN projects p ON p.id=c.project_id WHERE c.id=?');
            $q->execute([$caseId]);$case=$q->fetch(PDO::FETCH_ASSOC);
            if(!$case)bail('درخواست یافت نشد.',404);
            if($case['status']!=='submitted')bail('این درخواست قبلاً تعیین تکلیف شده است.',409);
            if($case['kind']==='execution' && actor()===(int)$case['requested_by'])
                bail('درخواست اجرای پراثر نیازمند تصمیم مدیر مستقل از ثبت‌کننده است.',403);
            if($decision==='approved' && $case['kind']==='execution' && !zmPmIsApproved((string)$case['project_title']))
                bail('طرح هنوز برچسب مصوب معتبر در پرونده ندارد.',409);
            if($decision==='approved'){
                $e=$db->prepare('SELECT title,body FROM documents WHERE id=?');
                $e->execute([(int)$case['evidence_doc_id']]);$doc=$e->fetch(PDO::FETCH_ASSOC);
                if(!$doc) bail('سند پیوست موجود نیست.',409);
                $hash=hash('sha256',(string)$doc['title']."\n".(string)$doc['body']);
                if(!hash_equals((string)$case['evidence_sha256'],$hash))bail('سند مدرک پس از ثبت درخواست تغییر کرده است.',409);
                $link=$db->prepare("SELECT COUNT(*) FROM zm_project_links WHERE project_id=? AND source='document' AND reference=?");
                $link->execute([(int)$case['project_id'],(string)$case['evidence_doc_id']]);
                if(!(int)$link->fetchColumn())bail('پیوند سند به پروژه دیگر معتبر نیست.',409);
            }
            $change=$db->prepare("UPDATE zm_project_approval_cases SET status=?,reviewed_by=?,decision_note=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND status='submitted'");
            $change->execute([$decision,actor(),$note,$caseId]);
            if($change->rowCount()!==1)bail('این درخواست هم‌زمان تغییر کرده است.',409);
            $event=$db->prepare('INSERT INTO zm_project_approval_events(case_id,action,note,actor_id) VALUES(?,?,?,?)');
            $event->execute([$caseId,$decision,$note,actor()]);
            audit($db,'decision','project-approval',$caseId);
            $db->exec('COMMIT');$inTransaction=false;
        }catch(Throwable $e){
            if($inTransaction){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
            throw $e;
        }
        return;
    }
    if($action==='project_approval_withdraw'){
        zmGovRealActor($db,['admin','manager']);
        $caseId=zmGovPositiveId(req('case_id'));
        $note=zmPmClean(req('withdraw_note'),900);
        $db->exec('BEGIN IMMEDIATE');$inTransaction=true;
        try {
            zmGovRealActor($db,['admin','manager']);
            $q=$db->prepare('SELECT status,project_id,requested_by FROM zm_project_approval_cases WHERE id=?');
            $q->execute([$caseId]);$case=$q->fetch(PDO::FETCH_ASSOC);
            if(!$case)bail('درخواست وجود ندارد.',404);
            if($case['status']!=='submitted')bail('درخواست قابل پس‌گرفتن نیست.',409);
            if(role()!=='admin' && (int)$case['requested_by']!==actor())bail('فقط ثبت‌کننده یا مدیر اصلی می‌تواند درخواست را پس بگیرد.',403);
            $db->prepare("UPDATE zm_project_approval_cases SET status='withdrawn',updated_at=CURRENT_TIMESTAMP WHERE id=?")
               ->execute([$caseId]);
            $db->prepare("INSERT INTO zm_project_approval_events(case_id,action,note,actor_id) VALUES(?,'withdrawn',?,?)")
               ->execute([$caseId,$note,actor()]);
            audit($db,'withdraw','project-approval',$caseId);
            $db->exec('COMMIT');$inTransaction=false;
        }catch(Throwable $e){
            if($inTransaction){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
            throw $e;
        }
        return;
    }
    bail('اقدام مصوبات پروژه ناشناخته است.',403);
}
function zmGovDisplay(PDO $db,?int $projectId=null):void {
    authorize('view');
    zmGovSchema($db);
    if($projectId!==null){
        $p=$db->prepare('SELECT id,title,state FROM projects WHERE id=?');
        $p->execute([$projectId]);$project=$p->fetch(PDO::FETCH_ASSOC);
        if(!$project)bail('پروژه وجود ندارد.',404);
    }else{$project=null;}
    $args=$projectId!==null?[$projectId]:[];
    $where=$projectId!==null?' WHERE c.project_id=?':'';
    $rows=q($db,'SELECT c.*,p.title AS project_title,writer.username AS writer_name,judge.username AS judge_name,d.title AS evidence_title
        FROM zm_project_approval_cases c JOIN projects p ON p.id=c.project_id
        JOIN users writer ON writer.id=c.requested_by
        JOIN documents d ON d.id=c.evidence_doc_id
        LEFT JOIN users judge ON judge.id=c.reviewed_by'.$where.'
        ORDER BY c.id DESC LIMIT 120',$args);
    $labels=['submitted'=>'در انتظار تصمیم','approved'=>'تأیید داخلی ثبت‌شده','rejected'=>'ردشده','withdrawn'=>'پس‌گرفته‌شده'];
    echo '<section><h2>گردش مستند تصمیم‌های پروژه</h2><p class="muted">تأیید در این بخش تصمیم داخلی قابل ممیزی است؛ نه امضای حقوقی قرارداد، تعهد مالی، شروع کارخانه یا اثبات اجرای فیزیکی. برای اجازه اجرا، بررسی مستقل از درخواست‌کننده ضروری است.</p>';
    if($projectId!==null){
        echo '<p>پروژه: <strong>'.esc($project['title']).'</strong> · <a href="?page=project_links&amp;project_id='.$projectId.'">بازگشت به پرونده</a></p>';
        $hasClearance=zmGovHasExecutionClearance($db,$projectId);
        echo '<p>مجوز داخلی شروع اجرا با بازبینی مستقل: <strong>'.($hasClearance?'تصمیم تأییدشده موجود':'ثبت نشده').'</strong></p>';
    }
    echo '<div class="scroll"><table><tr><th>پروژه / پرونده</th><th>نوع</th><th>موضوع</th><th>وضعیت</th><th>مدرک</th><th>درخواست‌کننده</th><th>تصمیم‌گیر</th><th>توضیح / تاریخ</th></tr>';
    foreach($rows as $r){
        echo '<tr><td><a href="?page=project_governance&amp;project_id='.(int)$r['project_id'].'">'.esc($r['project_title']).'</a></td><td>'.($r['kind']==='execution'?'مجوز شروع اجرا':'بررسی مستندات').'</td><td>'.esc($r['subject']).'</td><td>'.esc($labels[$r['status']]??$r['status']).'</td><td>#'.(int)$r['evidence_doc_id'].' — '.esc($r['evidence_title']).'</td><td>'.esc($r['writer_name']).'</td><td>'.esc($r['judge_name']??'—').'</td><td>'.esc($r['decision_note']!==''?$r['decision_note']:$r['justification']).' · '.esc($r['created_at']).'</td></tr>';
    }
    if(!$rows)echo '<tr><td colspan="8">هیچ درخواست تأیید مستند مرتبط ثبت نشده است.</td></tr>';
    echo '</table></div></section>';
    if($projectId!==null && in_array(role(),['admin','manager'],true) &&
       !zmPmIsArchiveOnly((string)$project['title']) && $project['state']!=='done'){
        $docs=q($db,"SELECT d.id,d.title FROM documents d JOIN zm_project_links l ON l.source='document' AND l.reference=CAST(d.id AS TEXT)
            WHERE l.project_id=? ORDER BY d.id DESC LIMIT 100",[$projectId]);
        echo '<section><h2>درخواست بررسی با مدرک معتبر پروژه</h2><p class="muted">ابتدا سند مدرک را در همین پرونده ثبت یا پیوند دهید. بدون مدرکِ متصل درخواست ثبت نمی‌شود.</p>';
        if($docs){
            formBegin('project_approval_submit');
            echo '<input type="hidden" name="project_id" value="'.$projectId.'"><label>نوع تصمیم</label><select name="kind"><option value="documentation">تأیید مستندات اداری (بدون مجوز شروع عملیات)</option>';
            if(zmPmIsApproved((string)$project['title']))
                echo '<option value="execution">مجوز شروع اجرا (پراثر؛ نیازمند بررسی مستقل)</option>';
            echo '</select><label>مدرک موجود</label><select name="evidence_doc_id">';
            foreach($docs as $doc)echo '<option value="'.(int)$doc['id'].'">#'.(int)$doc['id'].' — '.esc($doc['title']).'</option>';
            echo '</select><label>موضوع تصمیم</label><input name="subject" required maxlength="160"><label>توجیه و دلایل بررسی</label><textarea name="justification" required maxlength="1200"></textarea><button>ثبت درخواست قابل پیگیری</button></form>';
        }else echo '<p>مدرک پیوندخورده‌ای برای ثبت درخواست وجود ندارد.</p>';
        echo '</section>';
    }
    if(role()==='admin' && $rows){
        echo '<section><h2>تصمیم مدیر اصلی</h2><p class="muted">مجوز اجرای پراثر توسط همان فرد درخواست‌کننده قابل تصویب نیست. تمام تصمیم‌ها با دلیل و تاریخچه ثبت می‌شوند.</p>';
        foreach($rows as $r){
            if($r['status']!=='submitted')continue;
            echo '<details><summary>درخواست #'.(int)$r['id'].' — '.esc($r['subject']).' ('.($r['kind']==='execution'?'پراثر':'اداری').')</summary>';
            formBegin('project_approval_decide');
            echo '<input type="hidden" name="case_id" value="'.(int)$r['id'].'">';
            if($projectId!==null)echo '<input type="hidden" name="project_id" value="'.$projectId.'">';
            echo '<label>تصمیم</label><select name="decision"><option value="approved">تأیید اداری</option><option value="rejected">رد مستند</option></select><label>دلیل تصمیم</label><textarea name="decision_note" required maxlength="1200"></textarea><button>ثبت تصمیم غیرقابل‌حذف</button></form></details>';
        }
        echo '</section>';
    }
    if($projectId!==null && in_array(role(),['admin','manager'],true)){
        $pending=q($db,"SELECT id,subject,requested_by FROM zm_project_approval_cases WHERE project_id=? AND status='submitted' ORDER BY id DESC LIMIT 20",[$projectId]);
        foreach($pending as $c){
            if(role()!=='admin' && (int)$c['requested_by']!==actor())continue;
            echo '<details><summary>پس‌گرفتن درخواست باز #'.(int)$c['id'].' — '.esc($c['subject']).'</summary>';
            formBegin('project_approval_withdraw');
            echo '<input type="hidden" name="case_id" value="'.(int)$c['id'].'"><input type="hidden" name="project_id" value="'.$projectId.'">';
            echo '<label>دلیل پس‌گرفتن</label><textarea name="withdraw_note" maxlength="900" required></textarea><button>ثبت پس‌گرفتن با ردپا</button></form></details>';
        }
    }
    if($projectId!==null){
        $events=q($db,'SELECT e.*,c.kind,c.subject,u.username FROM zm_project_approval_events e JOIN zm_project_approval_cases c ON c.id=e.case_id JOIN users u ON u.id=e.actor_id WHERE c.project_id=? ORDER BY e.id DESC LIMIT 100',[$projectId]);
        echo '<section><h2>تاریخچه تصمیم‌های پرونده</h2><div class="scroll"><table><tr><th>درخواست</th><th>رویداد</th><th>توضیح</th><th>ثبت‌کننده</th><th>زمان UTC</th></tr>';
        foreach($events as $e)echo '<tr><td>#'.(int)$e['case_id'].' — '.esc($e['subject']).'</td><td>'.esc($e['action']).'</td><td>'.esc($e['note']).'</td><td>'.esc($e['username']).'</td><td>'.esc($e['created_at']).'</td></tr>';
        if(!$events)echo '<tr><td colspan="5">تاریخچه‌ای برای این پرونده ثبت نشده است.</td></tr>';
        echo '</table></div></section>';
    }
}
function zmGovRender(PDO $db):void {
    $raw=$_GET['project_id']??'';
    if($raw===''){zmGovDisplay($db,null);return;}
    if(!is_string($raw))bail('شناسه پروژه معتبر نیست.',422);
    zmGovDisplay($db,zmGovPositiveId($raw));
}

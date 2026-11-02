<?php
declare(strict_types=1);
/** Additive project operations, no banking, commercial release or obligations. */
function zmPmSchema(PDO $db):void {
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_events (
      id INTEGER PRIMARY KEY,
      project_id INTEGER NOT NULL REFERENCES projects(id),
      old_state TEXT NOT NULL, new_state TEXT NOT NULL,
      reason TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_updates (
      id INTEGER PRIMARY KEY,
      project_id INTEGER NOT NULL REFERENCES projects(id),
      category TEXT NOT NULL CHECK(category IN ('progress','blocker','decision')),
      progress_pct INTEGER CHECK(progress_pct BETWEEN 0 AND 100),
      description TEXT NOT NULL,
      actor_id INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_project_events_by_id ON zm_project_events(project_id,id)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_project_updates_by_id ON zm_project_updates(project_id,id)');
}
function zmPmClean(string $s,int $max=800):string {
    $s=trim($s);
    if($s==='' || (function_exists('mb_strlen')?mb_strlen($s,'UTF-8'):strlen($s))>$max || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u',$s))
        bail('متن لازم است و نباید دارای نویسه کنترلی یا طول غیرمجاز باشد.',422);
    return $s;
}
function zmPmAllowed(string $current):array {
    return match($current) {
        'planned'=>['active','paused'],
        'active'=>['paused','done'],
        'paused'=>['planned','active'],
        default=>[],
    };
}
function zmPmHandle(PDO $db,string $action):void {
    if(!in_array(role(),['admin','manager'],true) || actor()<1)
        bail('تغییر وضعیت پروژه فقط برای مدیران مجاز است.',403);
    $idText=req('project_id');
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$idText))bail('شناسه پروژه نامعتبر است.',422);
    $id=filter_var($idText,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($id===false)bail('شناسه پروژه نامعتبر است.',422);
    $db->exec('BEGIN IMMEDIATE');
    $txn=true;
    try {
        // Role is revalidated from the live user record within the same transaction.
        $check=$db->prepare('SELECT role,active FROM users WHERE id=?');
        $check->execute([actor()]);$member=$check->fetch(PDO::FETCH_ASSOC);
        if(!$member||(int)$member['active']!==1||!in_array($member['role'],['admin','manager'],true))
            bail('مجوز مدیریت پروژه معتبر نیست.',403);
        $find=$db->prepare('SELECT id,state FROM projects WHERE id=?');
        $find->execute([$id]);$project=$find->fetch(PDO::FETCH_ASSOC);
        if(!$project)bail('پروژه یافت نشد.',404);
        if($action==='project_transition'){
            $expected=req('expected_state');
            $next=req('next_state');
            if($expected!==$project['state'] || !in_array($next,zmPmAllowed($expected),true))
                bail('وضعیت تغییر کرده یا انتقال انتخابی مجاز نیست؛ صفحه را تازه کنید.',409);
            $reason=zmPmClean(req('reason'),800);
            $update=$db->prepare('UPDATE projects SET state=? WHERE id=? AND state=?');
            $update->execute([$next,$id,$expected]);
            if($update->rowCount()!==1)bail('تداخل تغییر همزمان پروژه؛ دوباره بررسی کنید.',409);
            $event=$db->prepare('INSERT INTO zm_project_events(project_id,old_state,new_state,reason,actor_id) VALUES(?,?,?,?,?)');
            $event->execute([$id,$expected,$next,$reason,actor()]);
            $audit=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');
            $audit->execute([actor(),'transition','project',$id]);
        } elseif($action==='project_update'){
            $cat=req('category');if(!in_array($cat,['progress','blocker','decision'],true))bail('نوع گزارش نامعتبر است.');
            $description=zmPmClean(req('description'),1000);
            $pct=req('progress_pct');
            if($cat==='progress'){
                if(!preg_match('/^(?:100|[1-9]?[0-9])$/D',$pct))bail('پیشرفت باید عددی بین صفر تا صد باشد.');
                $progress=(int)$pct;
            } else {
                if($pct!=='')bail('درصد فقط در گزارش پیشرفت مجاز است.');
                $progress=null;
            }
            $insert=$db->prepare('INSERT INTO zm_project_updates(project_id,category,progress_pct,description,actor_id) VALUES(?,?,?,?,?)');
            $insert->execute([$id,$cat,$progress,$description,actor()]);
            $audit=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');
            $audit->execute([actor(),'note','project',$id]);
        } else bail('عملیات مدیریت پروژه شناخته نشد.',403);
        $db->exec('COMMIT');
        $txn=false;
    }catch(Throwable $e){
        if($txn){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
        throw $e;
    }
}
function zmPmRender(PDO $db):void {
    authorize('view');
    zmPmSchema($db);
    $labels=['planned'=>'برنامه‌ریزی','active'=>'فعال','paused'=>'متوقف','done'=>'خاتمه‌یافته'];
    $roles=['admin','manager'];$canManage=in_array(role(),$roles,true);
    $counts=['planned'=>0,'active'=>0,'paused'=>0,'done'=>0];
    foreach(q($db,'SELECT state,COUNT(*) n FROM projects GROUP BY state') as $r){
        if(isset($counts[$r['state']]))$counts[$r['state']]=(int)$r['n'];
    }
    echo '<section><h2>داشبورد مدیریت پروژه‌های شرکت</h2><p class="muted">وضعیت هر پروژه ثبت اداری است؛ به‌تنهایی مجوز هزینه، استخدام، آغاز عملیات واقعی یا اثبات اتمام کار نیست.</p><div class="grid">';
    foreach($counts as $key=>$n)echo '<div class="card"><div class="metric">'.$n.'</div>'.esc($labels[$key]).'</div>';
    echo '</div><p>کل پرونده‌ها: <strong>'.array_sum($counts).'</strong> · رویدادهای تغییر وضعیت: <strong>'.(int)one($db,'SELECT COUNT(*) FROM zm_project_events').'</strong> · گزارش‌های پیشرفت و موانع: <strong>'.(int)one($db,'SELECT COUNT(*) FROM zm_project_updates').'</strong></p></section>';
    $offsetText=(string)($_GET['offset']??'0');
    $offset=preg_match('/^(?:0|[1-9][0-9]{0,5})$/D',$offsetText)?min(100000,(int)$offsetText):0;
    $page=q($db,'SELECT p.id,p.title,p.owner,p.state,p.budget,
       (SELECT progress_pct FROM zm_project_updates WHERE project_id=p.id AND category="progress" ORDER BY id DESC LIMIT 1) AS recorded_progress
       FROM projects p ORDER BY p.id DESC LIMIT 40 OFFSET '.$offset);
    echo '<section><h2>پرونده‌های ثبت‌شده</h2><div class="scroll"><table><tr><th>شناسه</th><th>عنوان</th><th>مسئول</th><th>وضعیت</th><th>بودجه پیشنهادی (IRR)</th><th>آخرین درصد اظهاری</th>'.($canManage?'<th>تغییر وضعیت با دلیل</th>':'').'</tr>';
    foreach($page as $p){
        echo '<tr><td>'.(int)$p['id'].'</td><td>'.esc($p['title']).'</td><td>'.esc($p['owner']).'</td><td>'.esc($labels[$p['state']]??$p['state']).'</td><td>'.money((int)$p['budget']).'</td><td>'.($p['recorded_progress']===null?'ثبت نشده':(int)$p['recorded_progress'].'٪').'</td>';
        if($canManage){
            echo '<td>';
            $choices=zmPmAllowed((string)$p['state']);
            if($choices){
                formBegin('project_transition');
                echo '<input type="hidden" name="project_id" value="'.(int)$p['id'].'"><input type="hidden" name="expected_state" value="'.esc($p['state']).'"><select name="next_state" aria-label="وضعیت جدید پروژه">';
                foreach($choices as $next)echo '<option value="'.esc($next).'">'.esc($labels[$next]).'</option>';
                echo '</select><input name="reason" maxlength="800" required placeholder="دلیل مستند تغییر وضعیت"><button>ثبت تصمیم</button></form>';
            } else echo '<span class="muted">مختومه؛ تغییر وضعیت مجاز نیست</span>';
            echo '</td>';
        }
        echo '</tr>';
    }
    echo '</table></div><p>';
    if($offset>0)echo '<a href="?page=projects&offset='.max(0,$offset-40).'">صفحه پیشین</a> · ';
    if(count($page)===40)echo '<a href="?page=projects&offset='.($offset+40).'">صفحه بعدی</a>';
    echo '</p></section>';
    if($canManage){
        $all=q($db,'SELECT id,title,state FROM projects ORDER BY id DESC LIMIT 250');
        $options='';
        foreach($all as $p)$options.='<option value="'.(int)$p['id'].'">#'.(int)$p['id'].' · '.esc($p['title']).' ('.esc($labels[$p['state']]??$p['state']).')</option>';
        echo '<section><h2>ثبت پیشرفت، مانع یا تصمیم</h2><p class="muted">درصد پیشرفت خوداظهاری است و تأیید مستقل یا اجرای واقعی محسوب نمی‌شود. امکان افزودن گزارش وجود دارد اما گزارش قبلی بازنویسی نمی‌شود.</p>';
        formBegin('project_update');echo '<label>پروژه</label><select name="project_id" required>'.$options.'</select>';
        echo '<label>نوع گزارش</label><select name="category"><option value="progress">پیشرفت</option><option value="blocker">مانع</option><option value="decision">تصمیم</option></select>';
        echo '<label>درصد پیشرفت (فقط برای نوع پیشرفت؛ صفر تا صد)</label><input name="progress_pct" inputmode="numeric" placeholder="برای مانع یا تصمیم خالی بگذارید">';
        echo '<label>توضیح و شواهد</label><textarea name="description" maxlength="1000" required></textarea><button>ثبت گزارش غیرقابل‌حذف</button></form></section>';
    }
    echo '<section><h2>تاریخچه تغییر وضعیت پروژه‌ها</h2><div class="scroll"><table><tr><th>پروژه</th><th>از</th><th>به</th><th>دلیل</th><th>کاربر</th><th>تاریخ UTC</th></tr>';
    foreach(q($db,'SELECT e.*,p.title,u.username FROM zm_project_events e JOIN projects p ON e.project_id=p.id LEFT JOIN users u ON e.actor_id=u.id ORDER BY e.id DESC LIMIT 50') as $r)
        echo '<tr><td>'.esc($r['title']).'</td><td>'.esc($labels[$r['old_state']]??$r['old_state']).'</td><td>'.esc($labels[$r['new_state']]??$r['new_state']).'</td><td>'.esc($r['reason']).'</td><td>'.esc($r['username']).'</td><td>'.esc($r['created_at']).'</td></tr>';
    echo '</table></div></section>';
    echo '<section><h2>تاریخچه پیشرفت و موانع</h2><div class="scroll"><table><tr><th>پروژه</th><th>نوع</th><th>پیشرفت اظهاری</th><th>شرح</th><th>کاربر</th><th>زمان UTC</th></tr>';
    foreach(q($db,'SELECT v.*,p.title,u.username FROM zm_project_updates v JOIN projects p ON v.project_id=p.id LEFT JOIN users u ON v.actor_id=u.id ORDER BY v.id DESC LIMIT 50') as $r)
        echo '<tr><td>'.esc($r['title']).'</td><td>'.esc($r['category']).'</td><td>'.($r['progress_pct']===null?'—':(int)$r['progress_pct'].'٪').'</td><td>'.esc($r['description']).'</td><td>'.esc($r['username']).'</td><td>'.esc($r['created_at']).'</td></tr>';
    echo '</table></div></section>';
    if(role()!=='viewer'){
        echo '<section><h2>ایجاد پرونده پروژه</h2><p class="muted">بودجه صرفاً پیشنهادی است و ثبت آن پرداخت یا تعهد مالی ایجاد نمی‌کند.</p>';formBegin('project');
        echo '<div class="form"><div><label>عنوان</label><input name="title" required maxlength="160"></div><div><label>مسئول</label><input name="owner" required maxlength="120"></div><div><label>وضعیت</label><select name="state"><option value="planned">برنامه‌ریزی</option><option value="paused">متوقف</option></select></div><div><label>بودجه پیشنهادی ریالی</label><input name="budget" value="0"></div></div><button>ثبت پرونده بدون تعهد مالی</button></form></section>';
    }
}

<?php
declare(strict_types=1);
/** Zomorod Melal: real-user project assignments and read-only posted-ledger reporting. */
function zmOpsSchema(PDO $db):void {
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_milestone_assignments (
        milestone_id INTEGER PRIMARY KEY REFERENCES zm_project_milestones(id),
        assigned_user_id INTEGER NOT NULL REFERENCES users(id),
        assigned_by INTEGER NOT NULL REFERENCES users(id),
        assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS zm_project_milestone_assignment_events (
        id INTEGER PRIMARY KEY,
        milestone_id INTEGER NOT NULL REFERENCES zm_project_milestones(id),
        previous_user_id INTEGER REFERENCES users(id),
        assigned_user_id INTEGER NOT NULL REFERENCES users(id),
        changed_by INTEGER NOT NULL REFERENCES users(id),
        note TEXT NOT NULL,
        occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec('CREATE INDEX IF NOT EXISTS zm_assigned_user ON zm_project_milestone_assignments(assigned_user_id,milestone_id)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_assignment_events_milestone ON zm_project_milestone_assignment_events(milestone_id,id)');
}
function zmOpsActiveAssignee(PDO $db,string $raw):int {
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$raw))bail('شناسه مسئول معتبر نیست.',422);
    $uid=filter_var($raw,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($uid===false)bail('شناسه مسئول معتبر نیست.',422);
    $st=$db->prepare("SELECT id FROM users WHERE id=? AND active=1 AND role IN ('admin','manager','accountant')");
    $st->execute([$uid]);$valid=$st->fetchColumn();
    if($valid===false)bail('مسئول باید کاربر فعال و دارای نقش عملیاتی باشد؛ انتساب به کاربر فرضی مجاز نیست.',409);
    return (int)$valid;
}
function zmOpsAssignNew(PDO $db,int $milestoneId,string $requested):void {
    // Call only inside a parent BEGIN IMMEDIATE transaction, after new milestone insert.
    $assignee=zmOpsActiveAssignee($db,$requested===''?(string)actor():$requested);
    $db->prepare('INSERT INTO zm_project_milestone_assignments(milestone_id,assigned_user_id,assigned_by) VALUES(?,?,?)')
       ->execute([$milestoneId,$assignee,actor()]);
    $db->prepare('INSERT INTO zm_project_milestone_assignment_events(milestone_id,previous_user_id,assigned_user_id,changed_by,note) VALUES(?,NULL,?,?,?)')
       ->execute([$milestoneId,$assignee,actor(),'ایجاد تخصیص مسئول واقعی هنگام تعریف نقطه عطف']);
}
function zmOpsTransfer(PDO $db):void {
    if(!in_array(role(),['admin','manager'],true))bail('انتقال مسئولیت فقط با مدیر مجاز است.',403);
    $projectText=req('project_id');$mileText=req('milestone_id');
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$projectText)||
       !preg_match('/^[1-9][0-9]{0,17}$/D',$mileText))bail('شناسه پروژه یا اقدام نامعتبر است.');
    $projectId=filter_var($projectText,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    $mileId=filter_var($mileText,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($projectId===false||$mileId===false)bail('شناسه معتبر نیست.');
    $newUser=req('assigned_user_id');$reason=zmPmClean(req('note'),900);
    $db->exec('BEGIN IMMEDIATE');$begun=true;
    try {
        zmPiRequireActor($db,['admin','manager']);
        $find=$db->prepare('SELECT m.id,m.state,p.title,p.state AS project_state
                 FROM zm_project_milestones m JOIN projects p ON p.id=m.project_id
                 WHERE m.id=? AND p.id=?');
        $find->execute([$mileId,$projectId]);$m=$find->fetch(PDO::FETCH_ASSOC);
        if(!$m)bail('اقدام در این پروژه پیدا نشد.',404);
        if(!zmPmIsApproved((string)$m['title'])||$m['project_state']==='done')
            bail('ارجاع اجرایی برای پرونده فاقد مصوبه یا مختومه مجاز نیست.',409);
        if(in_array($m['state'],['done','cancelled'],true))bail('اقدام خاتمه‌یافته قابل ارجاع دوباره نیست.',409);
        $assignee=zmOpsActiveAssignee($db,$newUser);
        $old=$db->prepare('SELECT assigned_user_id FROM zm_project_milestone_assignments WHERE milestone_id=?');
        $old->execute([$mileId]);$previous=$old->fetchColumn();
        if($previous!==false && (int)$previous===$assignee)bail('این مسئول از قبل انتخاب شده است.',409);
        if($previous===false){
            $db->prepare('INSERT INTO zm_project_milestone_assignments(milestone_id,assigned_user_id,assigned_by) VALUES(?,?,?)')
               ->execute([$mileId,$assignee,actor()]);
        } else {
            $db->prepare('UPDATE zm_project_milestone_assignments SET assigned_user_id=?,assigned_by=?,assigned_at=CURRENT_TIMESTAMP WHERE milestone_id=?')
               ->execute([$assignee,actor(),$mileId]);
        }
        $db->prepare('INSERT INTO zm_project_milestone_assignment_events(milestone_id,previous_user_id,assigned_user_id,changed_by,note) VALUES(?,?,?,?,?)')
           ->execute([$mileId,$previous===false?null:(int)$previous,$assignee,actor(),$reason]);
        audit($db,'assignment','project',$projectId);
        $db->exec('COMMIT');$begun=false;
    }catch(Throwable $e){
        if($begun){try{$db->exec('ROLLBACK');}catch(Throwable $ignored){}}
        throw $e;
    }
}
function zmOpsUserOptions(PDO $db,int $selected=0):string {
    $html='';
    foreach(q($db,"SELECT id,username,role FROM users WHERE active=1 AND role IN ('admin','manager','accountant') ORDER BY username") as $u) {
        $id=(int)$u['id'];
        $html.='<option value="'.$id.'"'.($id===$selected?' selected':'').'>'.esc($u['username'].' ('.$u['role'].')').'</option>';
    }
    return $html;
}
function zmOpsAssignmentSection(PDO $db,int $projectId,bool $canEdit):void {
    zmOpsSchema($db);
    $rows=q($db,"SELECT m.id,m.title,m.due_date,m.state,a.assigned_user_id,u.username,
          (SELECT COUNT(*) FROM zm_project_milestone_assignment_events e WHERE e.milestone_id=m.id) AS changes
          FROM zm_project_milestones m
          LEFT JOIN zm_project_milestone_assignments a ON a.milestone_id=m.id
          LEFT JOIN users u ON u.id=a.assigned_user_id
          WHERE m.project_id=? ORDER BY m.due_date,m.id LIMIT 150",[$projectId]);
    echo '<section><h2>مسئولیت و ارجاع اقدامات پروژه</h2><p class="muted">مسئول باید کاربر فعال سامانه باشد. ثبت مسئولیت، استخدام یا تأیید اجرای واقعی نیست.</p>';
    echo '<div class="scroll"><table><tr><th>اقدام</th><th>مسئول سیستم</th><th>سررسید</th><th>وضعیت</th><th>سابقه ارجاع</th>';
    if($canEdit)echo '<th>انتقال با دلیل</th>';
    echo '</tr>';
    foreach($rows as $m){
        echo '<tr><td>'.esc($m['title']).'</td><td>'.esc($m['username']??'تعیین نشده').'</td><td>'.esc($m['due_date']).'</td><td>'.esc($m['state']).'</td><td>'.(int)$m['changes'].'</td>';
        if($canEdit){
            echo '<td>';
            if(!in_array($m['state'],['done','cancelled'],true)){
                formBegin('project_assignment');
                echo '<input type="hidden" name="project_id" value="'.$projectId.'"><input type="hidden" name="milestone_id" value="'.(int)$m['id'].'">';
                echo '<select name="assigned_user_id" aria-label="مسئول جدید">'.zmOpsUserOptions($db,(int)($m['assigned_user_id']??0)).'</select>';
                echo '<input name="note" required maxlength="900" placeholder="دلیل تغییر مسئول"><button>ثبت ارجاع</button></form>';
            } else echo 'مختومه';
            echo '</td>';
        }
        echo '</tr>';
    }
    if(!$rows)echo '<tr><td colspan="'.($canEdit?6:5).'">هنوز اقدام زمان‌دار دارای مسئول وجود ندارد.</td></tr>';
    echo '</table></div></section>';
    $history=q($db,'SELECT e.*,m.title,old.username AS old_name,new.username AS new_name,a.username AS by_name
          FROM zm_project_milestone_assignment_events e
          JOIN zm_project_milestones m ON m.id=e.milestone_id
          LEFT JOIN users old ON old.id=e.previous_user_id
          JOIN users new ON new.id=e.assigned_user_id
          JOIN users a ON a.id=e.changed_by
          WHERE m.project_id=? ORDER BY e.id DESC LIMIT 100',[$projectId]);
    echo '<section><h2>تاریخچه مسئولیت‌های ثبت‌شده</h2><div class="scroll"><table><tr><th>اقدام</th><th>قبلی</th><th>جدید</th><th>دلیل</th><th>ثبت‌کننده</th><th>زمان UTC</th></tr>';
    foreach($history as $h)echo '<tr><td>'.esc($h['title']).'</td><td>'.esc($h['old_name']??'—').'</td><td>'.esc($h['new_name']).'</td><td>'.esc($h['note']).'</td><td>'.esc($h['by_name']).'</td><td>'.esc($h['occurred_at']).'</td></tr>';
    if(!$history)echo '<tr><td colspan="6">هیچ انتقال یا تعیین مسئول ثبت نشده است.</td></tr>';
    echo '</table></div></section>';
}
function zmOpsFinanceReport(PDO $db,?int $onlyProject=null):void {
    if(!in_array(role(),['admin','accountant'],true))bail('گزارش مالی پروژه‌ها فقط برای مدیر و حسابدار مجاز است.',403);
    if($onlyProject!==null){
        $exists=$db->prepare('SELECT 1 FROM projects WHERE id=?');$exists->execute([$onlyProject]);
        if($exists->fetchColumn()===false)bail('پروژه یافت نشد.',404);
    }
    // Both link types can point to the same journal entry; count each entry ONCE.
    // Conflicting assignments are excluded from totals and displayed as a risk.
    $sql="WITH allocation AS (
      SELECT j.id AS journal_id,
        (SELECT l.project_id FROM zm_project_links l WHERE l.source='journal' AND l.reference=CAST(j.id AS TEXT) LIMIT 1) AS direct_project,
        (SELECT l.project_id FROM invoices i JOIN zm_project_links l
          ON l.source='invoice' AND l.reference=CAST(i.id AS TEXT)
          WHERE i.posted_entry=j.id ORDER BY i.id LIMIT 1) AS invoice_project,
        (SELECT COUNT(DISTINCT l.project_id) FROM invoices i JOIN zm_project_links l
          ON l.source='invoice' AND l.reference=CAST(i.id AS TEXT)
          WHERE i.posted_entry=j.id) AS invoice_project_count
      FROM journal_entries j
    ), effective AS (
      SELECT journal_id,COALESCE(direct_project,invoice_project) AS project_id,
        CASE WHEN invoice_project_count>1 OR
          (direct_project IS NOT NULL AND invoice_project IS NOT NULL AND direct_project!=invoice_project)
        THEN 1 ELSE 0 END AS conflict
      FROM allocation
    )
    SELECT e.project_id,p.title,l.currency,a.type,
      SUM(CASE WHEN a.type='expense' THEN l.debit-l.credit ELSE 0 END) AS booked_expense,
      SUM(CASE WHEN a.type='income' THEN l.credit-l.debit ELSE 0 END) AS booked_income,
      COUNT(DISTINCT e.journal_id) AS docs
    FROM effective e JOIN journal_lines l ON l.entry_id=e.journal_id
      JOIN ledger_accounts a ON a.id=l.account_id
      JOIN projects p ON p.id=e.project_id
    WHERE e.conflict=0 AND e.project_id IS NOT NULL
    GROUP BY e.project_id,p.title,l.currency,a.type
    ORDER BY e.project_id,l.currency,a.type";
    $rows=$db->query($sql)->fetchAll(PDO::FETCH_ASSOC);
    $conflicts=(int)one($db,"WITH a AS (
       SELECT j.id AS j_id,
       (SELECT l.project_id FROM zm_project_links l WHERE l.source='journal' AND l.reference=CAST(j.id AS TEXT) LIMIT 1) AS direct_id,
       (SELECT COUNT(DISTINCT l.project_id) FROM invoices i JOIN zm_project_links l
          ON l.source='invoice' AND l.reference=CAST(i.id AS TEXT) WHERE i.posted_entry=j.id) AS n,
       (SELECT l.project_id FROM invoices i JOIN zm_project_links l
          ON l.source='invoice' AND l.reference=CAST(i.id AS TEXT) WHERE i.posted_entry=j.id ORDER BY i.id LIMIT 1) AS invoice_id
       FROM journal_entries j)
       SELECT COUNT(*) FROM a WHERE n>1 OR (direct_id IS NOT NULL AND invoice_id IS NOT NULL AND direct_id!=invoice_id)");
    echo '<section><h2>گزارش مالی تفکیکی پروژه‌ها — فقط اسناد قطعی دفترکل</h2>';
    echo '<p class="muted">فقط ردیف‌های ثبت‌شده واقعی دفترکل با پیوند معتبر به پروژه شمرده می‌شوند. فاکتور متصل به سند و همان سند متصل به پروژه هرگز دو بار شمرده نمی‌شوند. این گزارش اثبات وصول پول، تسویه بانک، تخصیص بودجه یا سود نقدی نیست.</p>';
    echo '<p>اسناد دارای انتساب متعارض که از تجمیع حذف شدند: <strong>'.$conflicts.'</strong></p>';
    echo '<div class="scroll"><table><tr><th>پروژه</th><th>ارز</th><th>نوع حساب</th><th>هزینه دفتری خالص</th><th>درآمد دفتری خالص</th><th>شمار اسناد در این ردیف</th></tr>';
    $found=false;
    foreach($rows as $row){
        if($onlyProject!==null&&(int)$row['project_id']!==$onlyProject)continue;
        if(!in_array($row['type'],['expense','income'],true))continue;
        $found=true;
        echo '<tr><td><a href="?page=project_links&amp;project_id='.(int)$row['project_id'].'">'.esc($row['title']).'</a></td><td>'.esc($row['currency']).'</td><td>'.esc($row['type']==='expense'?'هزینه ثبت‌شده':'درآمد ثبت‌شده').'</td><td>'.money((int)$row['booked_expense']).'</td><td>'.money((int)$row['booked_income']).'</td><td>'.(int)$row['docs'].'</td></tr>';
    }
    if(!$found)echo '<tr><td colspan="6">هیچ درآمد یا هزینه ثبت‌شده و قابل انتساب به این پروژه‌ها وجود ندارد.</td></tr>';
    echo '</table></div><p class="muted">ارقام ارزهای مختلف جمع نمی‌شوند؛ مبلغ منفی در اصلاحات حسابداری ممکن است و باید با مستندات بررسی شود.</p></section>';
}
function zmOpsFinanceRoute(PDO $db):void {
    $id=(string)($_GET['project_id']??'');
    if($id===''){zmOpsFinanceReport($db,null);return;}
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$id))bail('شناسه پروژه نامعتبر است.',422);
    $value=filter_var($id,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($value===false)bail('شناسه پروژه نامعتبر است.',422);
    zmOpsFinanceReport($db,$value);
}

function zmOpsAssignmentsDesk(PDO $db):void {
    authorize('view');
    zmOpsSchema($db);
    $isAdmin=role()==='admin';
    $today=today();
    $base="FROM zm_project_milestones m
       JOIN projects p ON p.id=m.project_id
       LEFT JOIN zm_project_milestone_assignments x ON x.milestone_id=m.id
       LEFT JOIN users u ON u.id=x.assigned_user_id
       WHERE m.state NOT IN ('done','cancelled')";
    $bind=$isAdmin?[]:[actor()];
    if(!$isAdmin)$base.=" AND x.assigned_user_id=?";
    $open=(int)one($db,'SELECT COUNT(*) '.$base,$bind);
    $overdueArgs=array_merge($bind,[$today]);
    $overdue=(int)one($db,'SELECT COUNT(*) '.$base.' AND m.due_date<?',$overdueArgs);
    $items=q($db,'SELECT m.id,m.project_id,p.title AS project_title,m.title,m.state,m.due_date,
            u.username,x.assigned_user_id,u.active
            '.$base.' ORDER BY m.due_date ASC,m.id ASC LIMIT 150',$bind);
    echo '<section><h2>'.($isAdmin?'کارتابل مسئولیت‌های پروژه‌های شرکت':'اقدامات تخصیص‌یافته به من').'</h2>';
    echo '<p>اقدامات باز: <strong>'.$open.'</strong> · دارای سررسید گذشته: <strong>'.$overdue.'</strong></p>';
    echo '<p class="muted">این لیست با حساب کاربری واقعی سامانه مرتبط است و به معنی اشتغال، پرداخت یا انجام فیزیکی کار نیست. اقدامات بدون مسئول باید توسط مدیر تعیین تکلیف شوند.</p>';
    echo '<p><a href="?page=projects">فهرست پروژه‌ها</a> · <a href="?page=project_calendar">تقویم پروژه‌ها</a></p>';
    echo '<div class="scroll"><table><tr><th>پروژه</th><th>اقدام</th><th>مسئول</th><th>سررسید</th><th>وضعیت</th></tr>';
    foreach($items as $r){
        $name=$r['username']??'فاقد مسئول ثبت‌شده';
        if($r['active']!==null && (int)$r['active']===0)$name.=' (حساب غیرفعال)';
        echo '<tr><td><a href="?page=project_links&amp;project_id='.(int)$r['project_id'].'">'.esc($r['project_title']).'</a></td><td>'.esc($r['title']).'</td><td>'.esc($name).'</td><td>'.esc($r['due_date']).($r['due_date']<$today?' (معوق)':'').'</td><td>'.esc($r['state']).'</td></tr>';
    }
    if(!$items)echo '<tr><td colspan="5">اقدام باز قابل نمایش وجود ندارد.</td></tr>';
    echo '</table></div></section>';
}

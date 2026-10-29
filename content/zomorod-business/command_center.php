<?php
declare(strict_types=1);
/**
 * Zomorod Melal | private owner command center, v1.
 * This file MUST remain outside public_html. It never sends money,
 * writes to the accounting DB, executes shell commands, or schedules jobs.
 */
function zmCcDb(string $private): PDO {
    if (!is_dir($private) || is_link($private)) throw new RuntimeException('Private company storage unavailable');
    $file = $private.'/command-center.sqlite3';
    if (is_link($file)) throw new RuntimeException('Unsafe control database link');
    $previous = umask(0077);
    try {
        $db = new PDO('sqlite:'.$file, null, null, [
            PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT=>12,
        ]);
        if (!chmod($file, 0600)) throw new RuntimeException('Cannot protect control database');
    } finally { umask($previous); }
    $db->exec('PRAGMA busy_timeout=12000; PRAGMA foreign_keys=ON;');
    $db->exec("CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        request_key TEXT NOT NULL UNIQUE,
        source_key TEXT UNIQUE,
        workstream TEXT NOT NULL CHECK(workstream IN ('company','finance','sales','inventory','personnel','projects','research','operations')),
        title TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        priority TEXT NOT NULL CHECK(priority IN ('normal','high','critical')),
        state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','in_progress','blocked','done','cancelled')),
        actor_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closing_note TEXT NOT NULL DEFAULT ''
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS task_events (
        id INTEGER PRIMARY KEY,
        task_id INTEGER NOT NULL REFERENCES tasks(id),
        actor_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE INDEX IF NOT EXISTS task_events_by_task ON task_events(task_id,id)");
    $db->exec("CREATE INDEX IF NOT EXISTS tasks_queue ON tasks(state,priority,id)");
    return $db;
}
function zmCcRequireAdmin(): void {
    if (!function_exists('actor') || !function_exists('role') || actor() <= 0 || role() !== 'admin') {
        bail('فقط مدیر اصلی به مرکز فرمان دسترسی دارد.', 403);
    }
}
function zmCcCreate(PDO $control, string $key, ?string $source, string $stream, string $title, string $detail, string $priority, int $uid): bool {
    $allowed=['company','finance','sales','inventory','personnel','projects','research','operations'];
    if (!preg_match('/^[a-f0-9]{32}$/D', $key) || !in_array($stream,$allowed,true) ||
        !in_array($priority,['normal','high','critical'],true) ||
        trim($title)==='' || mbSafeLen($title)>160 || mbSafeLen($detail)>2000) {
        bail('دستور مدیریتی نامعتبر است.', 422);
    }
    $control->beginTransaction();
    try {
        $insert=$control->prepare(
            "INSERT OR IGNORE INTO tasks(request_key,source_key,workstream,title,detail,priority,actor_id)
             VALUES(?,?,?,?,?,?,?)");
        $insert->execute([$key,$source,$stream,$title,$detail,$priority,$uid]);
        $created=$insert->rowCount()===1;
        if ($created) {
            $id=(int)$control->lastInsertId();
            $control->prepare("INSERT INTO task_events(task_id,actor_id,kind,note) VALUES(?,?,?,?)")
                ->execute([$id,$uid,'created','کار ایجاد شد؛ هیچ اجرای خودکار مجاز نشده است.']);
        }
        $control->commit();
        return $created;
    } catch (Throwable $e) {
        if ($control->inTransaction()) $control->rollBack();
        throw $e;
    }
}
function zmCcScan(PDO $company, PDO $control, int $uid): array {
    // This operation reads company tables and only creates local control-plane tasks.
    // No business ledger rows, invoices, payments, balances or inventory are mutated.
    $due=q($company,
        "SELECT i.id,i.invoice_no,i.kind,i.currency,i.due_date,i.amount,
                COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0) paid
         FROM invoices i
         WHERE i.due_date < ? AND i.amount >
               COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0)
         ORDER BY i.due_date,i.id LIMIT 20", [gmdate('Y-m-d')]);
    $stock=q($company,
        "SELECT i.id,i.sku,i.name,i.reorder_level,COALESCE(SUM(m.qty),0) qty
         FROM inventory i LEFT JOIN inventory_movements m ON m.inventory_id=i.id
         WHERE i.reorder_level>0
         GROUP BY i.id HAVING COALESCE(SUM(m.qty),0)<=i.reorder_level
         ORDER BY qty,i.id LIMIT 20");
    $created=0;
    foreach ($due as $item) {
        $source='invoice:'.(int)$item['id'];
        $title=($item['kind']==='sale'?'پیگیری وصول فاکتور ':'پیگیری پرداخت فاکتور ').$item['invoice_no'];
        $detail='سررسید: '.$item['due_date'].' | ارز: '.$item['currency'].
            ' | مانده: '.money((int)$item['amount']-(int)$item['paid']);
        $key=substr(hash('sha256','zm-cc-v1:'.$source),0,32);
        if (zmCcCreate($control,$key,$source,'finance',$title,$detail,'high',$uid)) $created++;
    }
    foreach ($stock as $item) {
        $source='stock:'.(int)$item['id'];
        $title='بررسی موجودی کالا: '.$item['sku'].' — '.$item['name'];
        $detail='موجودی: '.(int)$item['qty'].' | نقطه سفارش: '.(int)$item['reorder_level'];
        $key=substr(hash('sha256','zm-cc-v1:'.$source),0,32);
        if (zmCcCreate($control,$key,$source,'inventory',$title,$detail,'high',$uid)) $created++;
    }
    return ['created'=>$created,'inspected'=>count($due)+count($stock)];
}
function zmCcTransition(PDO $control, int $id, string $state, string $note, int $uid): void {
    if ($id<=0 || !in_array($state,['in_progress','blocked','done','cancelled'],true) ||
        mbSafeLen($note)>1000 || (($state==='done'||$state==='blocked'||$state==='cancelled')&&trim($note)==='')) {
        bail('وضعیت یا توضیح اقدام نامعتبر است.',422);
    }
    $control->beginTransaction();
    try {
        $get=$control->prepare('SELECT state FROM tasks WHERE id=?');
        $get->execute([$id]);
        $previous=$get->fetchColumn();
        if (!is_string($previous)) bail('وظیفه پیدا نشد.',404);
        $transitions=[
            'queued'=>['in_progress','blocked','cancelled'],
            'in_progress'=>['blocked','done','cancelled'],
            'blocked'=>['in_progress','cancelled'],
            'done'=>[],
            'cancelled'=>[],
        ];
        if (!in_array($state,$transitions[$previous]??[],true)) bail('تغییر وضعیت مجاز نیست.',409);
        $control->prepare('UPDATE tasks SET state=?,closing_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?')
            ->execute([$state,$note,$id]);
        $control->prepare('INSERT INTO task_events(task_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$uid,$state,$note]);
        $control->commit();
    } catch (Throwable $e) {
        if ($control->inTransaction()) $control->rollBack();
        throw $e;
    }
}
function zmCcHandle(PDO $company, PDO $control, string $action): void {
    zmCcRequireAdmin();
    $uid=actor();
    if ($action==='cc_create') {
        zmCcCreate($control,req('request_key'),null,req('workstream'),req('title'),req('detail'),req('priority','normal'),$uid);
    } elseif ($action==='cc_scan') {
        $result=zmCcScan($company,$control,$uid);
        $_SESSION['cc_result']='موارد بررسی‌شده: '.$result['inspected'].' | وظایف جدید: '.$result['created'];
    } elseif ($action==='cc_transition') {
        zmCcTransition($control,(int)req('task_id'),req('state'),req('note'),$uid);
    } else {
        bail('عملیات مرکز فرمان ناشناخته است.',403);
    }
}
function zmCcRender(PDO $control): void {
    zmCcRequireAdmin();
    $states=['queued'=>'در صف','in_progress'=>'در حال پیگیری','blocked'=>'مسدود','done'=>'انجام‌شده','cancelled'=>'لغوشده'];
    $streams=['company'=>'مدیریت شرکت','finance'=>'مالی','sales'=>'فروش','inventory'=>'انبار','personnel'=>'پرسنل','projects'=>'پروژه‌ها','research'=>'پژوهش','operations'=>'عملیات'];
    $stats=q($control,'SELECT state,COUNT(*) count FROM tasks GROUP BY state ORDER BY state');
    echo '<section><h2>مرکز فرمان هوشمند شرکت — نسخهٔ پایه</h2>';
    echo '<p class="muted">فرمان‌ها در حافظهٔ عملیاتی خصوصی ذخیره می‌شوند. این نسخه فقط ثبت، پیگیری و شناسایی کارها را انجام می‌دهد؛ هیچ وظیفهٔ ساعتی، پرداخت یا اقدام خارجی خودکار فعال نیست.</p>';
    if(isset($_SESSION['cc_result'])){echo '<div class="notice">'.esc($_SESSION['cc_result']).'</div>';unset($_SESSION['cc_result']);}
    echo '<div class="grid">';
    foreach($stats as $v)echo '<div class="card"><div class="metric">'.(int)$v['count'].'</div>'.esc($states[$v['state']]??$v['state']).'</div>';
    echo '</div>';
    formBegin('cc_scan');echo '<button type="submit">بررسی دستی فاکتورهای معوق و کسری انبار</button></form>';
    echo '<p class="muted">این بررسی فقط کارهای قابل پیگیری ایجاد می‌کند و فاکتور یا موجودی را تغییر نمی‌دهد.</p></section>';
    echo '<section><h2>ثبت دستور جدید مدیرعامل</h2>';formBegin('cc_create');
    echo '<input type="hidden" name="request_key" value="'.bin2hex(random_bytes(16)).'">';
    echo '<div class="form"><div><label>واحد مسئول</label><select name="workstream">';
    foreach($streams as $v=>$label) echo '<option value="'.esc($v).'">'.esc($label).'</option>';
    echo '</select></div><div><label>اولویت</label><select name="priority"><option value="normal">عادی</option><option value="high">بالا</option><option value="critical">بحرانی</option></select></div>';
    echo '<div class="full"><label>عنوان وظیفه</label><input name="title" maxlength="160" required></div>';
    echo '<div class="full"><label>شرح و معیار خروجی</label><textarea name="detail" maxlength="2000" required></textarea></div></div>';
    echo '<button>ثبت در صف پیگیری</button></form></section>';
    echo '<section><h2>صف وظایف ماندگار</h2><div class="scroll"><table><thead><tr><th>شناسه</th><th>وظیفه</th><th>واحد</th><th>اولویت</th><th>وضعیت</th><th>تاریخ</th><th>اقدام مدیریتی</th></tr></thead><tbody>';
    $tasks=q($control,"SELECT * FROM tasks ORDER BY CASE state WHEN 'queued' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'blocked' THEN 2 ELSE 3 END,
        CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,id DESC LIMIT 80");
    foreach($tasks as $t){
        echo '<tr><td>'.(int)$t['id'].'</td><td><strong>'.esc($t['title']).'</strong><p class="muted">'.esc($t['detail']).'</p></td><td>'.esc($streams[$t['workstream']]??$t['workstream']).'</td><td>'.esc($t['priority']).'</td><td>'.esc($states[$t['state']]??$t['state']).'</td><td>'.esc($t['created_at']).'</td><td>';
        if(in_array($t['state'],['queued','in_progress','blocked'],true)){
            formBegin('cc_transition');
            echo '<input type="hidden" name="task_id" value="'.(int)$t['id'].'">';
            echo '<select name="state">';
            $choices=$t['state']==='queued'?['in_progress','blocked','cancelled']:($t['state']==='blocked'?['in_progress','cancelled']:['blocked','done','cancelled']);
            foreach($choices as $v)echo '<option value="'.esc($v).'">'.esc($states[$v]).'</option>';
            echo '</select><label>توضیح و شواهد اقدام</label><input name="note" maxlength="1000" placeholder="علت / نتیجه / مرجع قابل بررسی"><button>ثبت تغییر وضعیت</button></form>';
        }else echo esc($t['closing_note']);
        echo '</td></tr>';
    }
    if(!$tasks)echo '<tr><td colspan="7">هنوز دستوری ثبت نشده است.</td></tr>';
    echo '</tbody></table></div></section>';
    echo '<section><h2>آخرین رخدادهای مرکز فرمان</h2><div class="scroll"><table><tr><th>وظیفه</th><th>نوع</th><th>کاربر</th><th>توضیح</th><th>زمان</th></tr>';
    foreach(q($control,'SELECT * FROM task_events ORDER BY id DESC LIMIT 35') as $event){
        echo '<tr><td>'.(int)$event['task_id'].'</td><td>'.esc($event['kind']).'</td><td>'.(int)$event['actor_id'].'</td><td>'.esc($event['note']).'</td><td>'.esc($event['recorded_at']).'</td></tr>';
    }
    echo '</table></div></section>';
}

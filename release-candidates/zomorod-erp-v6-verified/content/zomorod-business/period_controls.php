<?php
declare(strict_types=1);
/** Private company accounting-period freeze. No external payment, signatures or tax filing.
 * Works in the SAME SQLite ledger transaction as journal postings; do not split into a sidecar DB.
 */
function zmPeriodSchema(PDO $db): void {
    $db->exec("CREATE TABLE IF NOT EXISTS zm_accounting_periods (
        period_key TEXT PRIMARY KEY CHECK(length(period_key)=7),
        state TEXT NOT NULL CHECK(state IN ('pending','closed')),
        requested_by INTEGER NOT NULL REFERENCES users(id),
        approved_by INTEGER REFERENCES users(id),
        snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64),
        request_note TEXT NOT NULL,
        decision_note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT
    )");
    $db->exec("CREATE TABLE IF NOT EXISTS zm_period_events (
        id INTEGER PRIMARY KEY,
        period_key TEXT NOT NULL REFERENCES zm_accounting_periods(period_key),
        actor_id INTEGER NOT NULL REFERENCES users(id),
        event TEXT NOT NULL CHECK(event IN ('freeze_requested','period_closed')),
        note TEXT NOT NULL,
        at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_events_no_update BEFORE UPDATE ON zm_period_events
        BEGIN SELECT RAISE(ABORT,'Immutable period audit events'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_events_no_delete BEFORE DELETE ON zm_period_events
        BEGIN SELECT RAISE(ABORT,'Immutable period audit events'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_periods_no_delete BEFORE DELETE ON zm_accounting_periods
        BEGIN SELECT RAISE(ABORT,'Period records are permanent'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_insert_only_pending
        BEFORE INSERT ON zm_accounting_periods
        WHEN NEW.state!='pending' OR NEW.approved_by IS NOT NULL
        BEGIN SELECT RAISE(ABORT,'Accounting periods must begin pending'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_immutable_transition
        BEFORE UPDATE ON zm_accounting_periods
        WHEN NOT (OLD.state='pending' AND NEW.state='closed'
            AND OLD.period_key=NEW.period_key AND OLD.requested_by=NEW.requested_by
            AND OLD.snapshot_sha256=NEW.snapshot_sha256 AND OLD.request_note=NEW.request_note
            AND NEW.approved_by IS NOT NULL AND NEW.approved_by!=OLD.requested_by
            AND length(trim(NEW.decision_note))>0)
        BEGIN SELECT RAISE(ABORT,'Invalid accounting period transition'); END");
    // DB-level protection: legacy entrypoints cannot bypass the PHP guard.
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_entry_insert
        BEFORE INSERT ON journal_entries
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.doc_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_entry_update
        BEFORE UPDATE ON journal_entries
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.doc_date,1,7))
          OR EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.doc_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_entry_delete
        BEFORE DELETE ON journal_entries
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.doc_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_line_insert
        BEFORE INSERT ON journal_lines
        WHEN EXISTS(SELECT 1 FROM journal_entries e JOIN zm_accounting_periods p
                    ON p.period_key=substr(e.doc_date,1,7) WHERE e.id=NEW.entry_id)
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_line_update
        BEFORE UPDATE ON journal_lines
        WHEN EXISTS(SELECT 1 FROM journal_entries e JOIN zm_accounting_periods p
                    ON p.period_key=substr(e.doc_date,1,7) WHERE e.id=OLD.entry_id)
          OR EXISTS(SELECT 1 FROM journal_entries e JOIN zm_accounting_periods p
                    ON p.period_key=substr(e.doc_date,1,7) WHERE e.id=NEW.entry_id)
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_line_delete
        BEFORE DELETE ON journal_lines
        WHEN EXISTS(SELECT 1 FROM journal_entries e JOIN zm_accounting_periods p
                    ON p.period_key=substr(e.doc_date,1,7) WHERE e.id=OLD.entry_id)
        BEGIN SELECT RAISE(ABORT,'Ledger period is frozen'); END");
    // Prevent attaching two business documents to the same journal posting.
    // Legacy data are NOT rewritten; the independent audit finds existing conflicts.
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_unique_invoice_posting_insert
        BEFORE INSERT ON invoices
        WHEN EXISTS(SELECT 1 FROM invoices WHERE posted_entry=NEW.posted_entry)
          OR EXISTS(SELECT 1 FROM invoice_payments WHERE entry_id=NEW.posted_entry)
        BEGIN SELECT RAISE(ABORT,'Accounting posting already linked to another document'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_unique_invoice_posting_update
        BEFORE UPDATE OF posted_entry ON invoices
        WHEN EXISTS(SELECT 1 FROM invoices WHERE posted_entry=NEW.posted_entry AND id!=OLD.id)
          OR EXISTS(SELECT 1 FROM invoice_payments WHERE entry_id=NEW.posted_entry)
        BEGIN SELECT RAISE(ABORT,'Accounting posting already linked to another document'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_unique_payment_posting_insert
        BEFORE INSERT ON invoice_payments
        WHEN EXISTS(SELECT 1 FROM invoices WHERE posted_entry=NEW.entry_id)
          OR EXISTS(SELECT 1 FROM invoice_payments WHERE entry_id=NEW.entry_id)
        BEGIN SELECT RAISE(ABORT,'Accounting posting already linked to another document'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_unique_payment_posting_update
        BEFORE UPDATE OF entry_id ON invoice_payments
        WHEN EXISTS(SELECT 1 FROM invoices WHERE posted_entry=NEW.entry_id)
          OR EXISTS(SELECT 1 FROM invoice_payments WHERE entry_id=NEW.entry_id AND id!=OLD.id)
        BEGIN SELECT RAISE(ABORT,'Accounting posting already linked to another document'); END");
    // Defend related source documents as well as their posted journal lines.
    // An open-month payment on an old, closed invoice is allowed: paid_on governs.
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_invoice_insert
        BEFORE INSERT ON invoices
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.invoice_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Invoice accounting period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_invoice_update
        BEFORE UPDATE ON invoices
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.invoice_date,1,7))
          OR EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.invoice_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Invoice accounting period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_invoice_delete
        BEFORE DELETE ON invoices
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.invoice_date,1,7))
        BEGIN SELECT RAISE(ABORT,'Invoice accounting period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_payment_insert
        BEFORE INSERT ON invoice_payments
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.paid_on,1,7))
        BEGIN SELECT RAISE(ABORT,'Payment accounting period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_payment_update
        BEFORE UPDATE ON invoice_payments
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.paid_on,1,7))
          OR EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(NEW.paid_on,1,7))
        BEGIN SELECT RAISE(ABORT,'Payment accounting period is frozen'); END");
    $db->exec("CREATE TRIGGER IF NOT EXISTS zm_period_guard_payment_delete
        BEFORE DELETE ON invoice_payments
        WHEN EXISTS(SELECT 1 FROM zm_accounting_periods WHERE period_key=substr(OLD.paid_on,1,7))
        BEGIN SELECT RAISE(ABORT,'Payment accounting period is frozen'); END");
}
function zmPeriodKey(string $date): string {
    if(!preg_match('/^20[0-9]{2}-(?:0[1-9]|1[0-2])-[0-3][0-9]$/D',$date) ||
       !DateTimeImmutable::createFromFormat('!Y-m-d',$date) ||
       DateTimeImmutable::createFromFormat('!Y-m-d',$date)->format('Y-m-d')!==$date) {
        bail('تاریخ دورهٔ مالی نامعتبر است.',422);
    }
    return substr($date,0,7);
}
function zmPeriodGuard(PDO $db,string $date): void {
    $month=zmPeriodKey($date);
    $s=$db->prepare('SELECT state FROM zm_accounting_periods WHERE period_key=?');
    $s->execute([$month]);
    if($s->fetchColumn()!==false) bail('این دورهٔ مالی در حال بستن یا بسته‌شده است؛ ثبت سند مجاز نیست.',409);
}
function zmPeriodFingerprint(PDO $db,string $month): array {
    if(!preg_match('/^20[0-9]{2}-(?:0[1-9]|1[0-2])$/D',$month)) bail('دورهٔ مالی نامعتبر است.',422);
    $from=$month.'-01';$to=(new DateTimeImmutable($from))->modify('+1 month')->format('Y-m-d');
    $s=$db->prepare("SELECT e.id,e.doc_no,e.doc_date,l.id line_id,l.account_id,l.currency,l.debit,l.credit
        FROM journal_entries e LEFT JOIN journal_lines l ON l.entry_id=e.id
        WHERE e.doc_date>=? AND e.doc_date<? ORDER BY e.id,l.id");
    $s->execute([$from,$to]);$rows=$s->fetchAll(PDO::FETCH_ASSOC);
    $entryCount=0;$lineCount=0;$perEntry=[];
    foreach($rows as $r){
        $id=(int)$r['id'];
        if(!isset($perEntry[$id])){$entryCount++;$perEntry[$id]=['lines'=>0,'sums'=>[]];}
        if($r['line_id']===null)continue;
        $lineCount++;$perEntry[$id]['lines']++;
        $cur=(string)$r['currency'];
        if(!isset($perEntry[$id]['sums'][$cur]))$perEntry[$id]['sums'][$cur]=[0,0];
        $perEntry[$id]['sums'][$cur][0]+=(int)$r['debit'];
        $perEntry[$id]['sums'][$cur][1]+=(int)$r['credit'];
    }
    if($entryCount===0) bail('بستن دورهٔ خالی بدون بررسی اختصاصی مجاز نیست.',409);
    foreach($perEntry as $record){
        if($record['lines']<2) bail('سند مالی ناقص است.',409);
        foreach($record['sums'] as [$debit,$credit]){
            if($debit<=0 || $debit!==$credit) bail('سند یا ارز نامتوازن است.',409);
        }
    }
    $digest=hash('sha256',json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
    return ['hash'=>$digest,'entries'=>$entryCount,'lines'=>$lineCount];
}
function zmPeriodNote(string $note): string {
    $note=trim($note);
    if($note==='' || mbSafeLen($note)>1000 || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u',$note))bail('دلیل یا شواهد تصمیم لازم است.',422);
    return $note;
}
function zmPeriodAction(PDO $db,string $action,string $month,string $note,int $uid,string $access): void {
    if(!in_array($action,['period_freeze','period_close'],true)||
       !preg_match('/^20[0-9]{2}-(?:0[1-9]|1[0-2])$/D',$month)||$uid<=0) bail('عملیات دورهٔ مالی نامعتبر است.',422);
    $note=zmPeriodNote($note);
    if(!in_array($access,['accountant','admin'],true))bail('اختیار دورهٔ مالی ندارید.',403);
    $db->beginTransaction();
    try{
        if($action==='period_freeze'){
            $s=$db->prepare('SELECT state FROM zm_accounting_periods WHERE period_key=?');$s->execute([$month]);
            if($s->fetchColumn()!==false)bail('دوره قبلاً مسدود شده است.',409);
            $proof=zmPeriodFingerprint($db,$month);
            $db->prepare("INSERT INTO zm_accounting_periods(period_key,state,requested_by,snapshot_sha256,request_note)
                         VALUES(?,'pending',?,?,?)")->execute([$month,$uid,$proof['hash'],$note]);
            $db->prepare('INSERT INTO zm_period_events(period_key,actor_id,event,note) VALUES(?,?,?,?)')
                ->execute([$month,$uid,'freeze_requested','درخواست مسدودسازی: '.$note]);
        }else{
            if($access!=='admin')bail('تأیید نهایی فقط با مدیر مجاز است.',403);
            $s=$db->prepare('SELECT * FROM zm_accounting_periods WHERE period_key=?');$s->execute([$month]);$period=$s->fetch(PDO::FETCH_ASSOC);
            if(!$period || $period['state']!=='pending')bail('درخواست بستن دوره وجود ندارد.',409);
            if($uid===(int)$period['requested_by'])bail('بستن دوره به دو فرد مستقل نیاز دارد.',403);
            $proof=zmPeriodFingerprint($db,$month);
            if(!hash_equals((string)$period['snapshot_sha256'],$proof['hash']))bail('محتوای دوره از زمان درخواست تغییر کرده است.',409);
            $db->prepare("UPDATE zm_accounting_periods SET state='closed',approved_by=?,decision_note=?,closed_at=CURRENT_TIMESTAMP
                           WHERE period_key=? AND state='pending'")->execute([$uid,$note,$month]);
            $db->prepare('INSERT INTO zm_period_events(period_key,actor_id,event,note) VALUES(?,?,?,?)')
                ->execute([$month,$uid,'period_closed','تأیید کنترل مستقل: '.$note]);
        }
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmPeriodRender(PDO $db): void {
    authorize('account');
    echo '<section><h2>کنترل بستن دوره‌های حسابداری</h2><p class="muted">درخواست بستن دوره، ثبت سند جدید در همان ماه را فوراً مسدود می‌کند. تأیید نهایی نیازمند مدیر مستقل و کنترل توازن اسناد است. این بخش جایگزین حسابرسی رسمی یا تکالیف مالیاتی نیست.</p>';
    echo '<div class="scroll"><table><tr><th>ماه میلادی</th><th>وضعیت</th><th>درخواست‌دهنده</th><th>تأییدکننده</th><th>دلیل</th></tr>';
    foreach(q($db,'SELECT * FROM zm_accounting_periods ORDER BY period_key DESC LIMIT 60') as $r){
        echo '<tr><td>'.esc($r['period_key']).'</td><td>'.esc($r['state']).'</td><td>'.(int)$r['requested_by'].'</td><td>'.(int)$r['approved_by'].'</td><td>'.esc($r['decision_note']?:$r['request_note']).'</td></tr>';
    }
    echo '</table></div></section>';
    if(in_array(role(),['accountant','admin'],true)){
        echo '<section><h2>درخواست یا تأیید بستن دوره</h2>';
        formBegin('period_freeze');echo '<label>دوره YYYY-MM</label><input name="period_key" pattern="20[0-9]{2}-(0[1-9]|1[0-2])" maxlength="7" required>';
        echo '<label>دلیل و مرجع بررسی</label><textarea name="note" maxlength="1000" required></textarea><button>درخواست بستن</button></form>';
        if(role()==='admin'){
            foreach(q($db,"SELECT * FROM zm_accounting_periods WHERE state='pending' ORDER BY period_key DESC LIMIT 20") as $r){
                if((int)$r['requested_by']===actor())continue;
                formBegin('period_close');echo '<input type="hidden" name="period_key" value="'.esc($r['period_key']).'">';
                echo '<label>تأیید نهایی دوره '.esc($r['period_key']).'</label><input name="note" maxlength="1000" required placeholder="مرجع و کنترل دستی"><button>تأیید بستن دوره</button></form>';
            }
        }
        echo '</section>';
    }
}

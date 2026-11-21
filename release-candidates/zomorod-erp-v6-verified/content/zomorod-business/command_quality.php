<?php
declare(strict_types=1);
/** Private task planning and evidence gate. No executor, banking action or scheduler. */
function zmCcQualitySchema(PDO $db): void {
    $db->exec("CREATE TABLE IF NOT EXISTS task_quality (
        task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE RESTRICT,
        risk TEXT NOT NULL CHECK(risk IN ('read_only','internal_write','high_impact')),
        deliverable TEXT NOT NULL,
        acceptance TEXT NOT NULL,
        review_state TEXT NOT NULL DEFAULT 'planned'
            CHECK(review_state IN ('planned','submitted','approved','rejected')),
        evidence_url TEXT NOT NULL DEFAULT '',
        reviewer_id INTEGER,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )");
}
function zmCcQualityInput(string $value,int $max): string {
    $value=trim($value);
    if($value==='' || mbSafeLen($value)>$max || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/u',$value)) {
        bail('اطلاعات برنامه یا شواهد معتبر نیست.',422);
    }
    return $value;
}
function zmCcQualityPlan(PDO $db,int $id,string $risk,string $deliverable,string $acceptance,int $uid): void {
    if($id<=0 || !in_array($risk,['read_only','internal_write','high_impact'],true)) bail('طبقه‌بندی ریسک نامعتبر است.',422);
    $deliverable=zmCcQualityInput($deliverable,500);
    $acceptance=zmCcQualityInput($acceptance,1000);
    $db->beginTransaction();
    try {
        $s=$db->prepare('SELECT state FROM tasks WHERE id=?');$s->execute([$id]);
        $state=$s->fetchColumn();
        if(!is_string($state)||in_array($state,['done','cancelled'],true)) bail('وظیفه قابل برنامه‌ریزی نیست.',409);
        $s=$db->prepare('SELECT review_state FROM task_quality WHERE task_id=?');$s->execute([$id]);
        if($s->fetchColumn()!==false) bail('برای این وظیفه قبلاً برنامه ثبت شده است؛ برای جلوگیری از ازبین‌رفتن شواهد قابل بازنویسی نیست.',409);
        $db->prepare("INSERT INTO task_quality(task_id,risk,deliverable,acceptance) VALUES(?,?,?,?)")
            ->execute([$id,$risk,$deliverable,$acceptance]);
        $db->prepare('INSERT INTO task_events(task_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$uid,'quality_plan','برنامه و معیار پذیرش ثبت شد. سطح ریسک: '.$risk]);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmCcQualityEvidence(PDO $db,int $id,string $url,int $uid): void {
    $url=zmCcQualityInput($url,500);
    if(!filter_var($url,FILTER_VALIDATE_URL) || strtolower((string)parse_url($url,PHP_URL_SCHEME))!=='https' ||
        parse_url($url,PHP_URL_USER)!==null || parse_url($url,PHP_URL_PASS)!==null) {
        bail('مرجع شواهد باید پیوند HTTPS بدون رمز یا اطلاعات ورود باشد.',422);
    }
    $db->beginTransaction();
    try {
        $s=$db->prepare("SELECT t.state,q.review_state FROM tasks t JOIN task_quality q ON q.task_id=t.id WHERE t.id=?");
        $s->execute([$id]);$v=$s->fetch(PDO::FETCH_ASSOC);
        if(!$v||$v['state']!=='in_progress'||!in_array($v['review_state'],['planned','rejected'],true))
            bail('ابتدا برنامه و وضعیت درحال پیگیری لازم است.',409);
        $db->prepare("UPDATE task_quality SET evidence_url=?,review_state='submitted',reviewer_id=NULL,updated_at=CURRENT_TIMESTAMP WHERE task_id=?")
            ->execute([$url,$id]);
        $db->prepare('INSERT INTO task_events(task_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$uid,'evidence_submitted','مرجع شواهد ثبت شد؛ صحت محتوا هنوز تأیید نشده است.']);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmCcQualityReview(PDO $db,int $id,bool $approved,string $note,int $uid): void {
    $note=zmCcQualityInput($note,1000);
    $db->beginTransaction();
    try {
        $s=$db->prepare('SELECT t.state,q.review_state,q.evidence_url FROM tasks t JOIN task_quality q ON q.task_id=t.id WHERE t.id=?');
        $s->execute([$id]);$v=$s->fetch(PDO::FETCH_ASSOC);
        if(!$v||$v['state']!=='in_progress'||$v['review_state']!=='submitted'||$v['evidence_url']==='')
            bail('مدرک قابل داوری وجود ندارد.',409);
        $decision=$approved?'approved':'rejected';
        $db->prepare('UPDATE task_quality SET review_state=?,reviewer_id=?,updated_at=CURRENT_TIMESTAMP WHERE task_id=?')
            ->execute([$decision,$uid,$id]);
        $db->prepare('INSERT INTO task_events(task_id,actor_id,kind,note) VALUES(?,?,?,?)')
            ->execute([$id,$uid,'quality_'.$decision,$note]);
        $db->commit();
    }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
}
function zmCcQualityCompletionGate(PDO $db,int $id): void {
    // Existing v1 tasks without a plan keep their historical behaviour.
    // Once a plan exists, no "done" transition is permitted without explicit review.
    $s=$db->prepare('SELECT review_state FROM task_quality WHERE task_id=?');$s->execute([$id]);
    $state=$s->fetchColumn();
    if($state!==false && $state!=='approved')
        bail('تحویل نیازمند بررسی و تأیید شواهد ثبت‌شده است.',409);
}
function zmCcQualityHandle(PDO $db,string $action,int $uid): void {
    zmCcRequireAdmin();
    $id=(int)req('task_id');
    if($action==='cc_plan'){
        zmCcQualityPlan($db,$id,req('risk'),req('deliverable'),req('acceptance'),$uid);
    }elseif($action==='cc_evidence'){
        zmCcQualityEvidence($db,$id,req('evidence_url'),$uid);
    }elseif($action==='cc_review'){
        $decision=req('decision');
        if(!in_array($decision,['approve','reject'],true))bail('تصمیم نامعتبر است.',422);
        zmCcQualityReview($db,$id,$decision==='approve',req('review_note'),$uid);
    }else bail('عملیات کنترل کیفیت شناخته نشد.',403);
}
function zmCcQualityWidgets(PDO $db,int $id,array $t): void {
    $s=$db->prepare('SELECT * FROM task_quality WHERE task_id=?');$s->execute([$id]);
    $plan=$s->fetch(PDO::FETCH_ASSOC);
    if(!$plan) {
        if(!in_array($t['state'],['queued','in_progress','blocked'],true))return;
        echo '<details><summary>تعریف برنامه و معیار تحویل</summary>';
        formBegin('cc_plan');
        echo '<input type="hidden" name="task_id" value="'.$id.'">';
        echo '<label>طبقه ریسک</label><select name="risk"><option value="read_only">فقط‌خواندنی</option><option value="internal_write">ثبت داخلی</option><option value="high_impact">مالی/حقوقی/حساس — نیازمند تأیید</option></select>';
        echo '<label>خروجی مورد انتظار</label><textarea name="deliverable" maxlength="500" required></textarea>';
        echo '<label>معیار پذیرش قابل راستی‌آزمایی</label><textarea name="acceptance" maxlength="1000" required></textarea>';
        echo '<button>ثبت برنامه</button></form></details>';
        return;
    }
    $states=['planned'=>'در انتظار مدرک','submitted'=>'شواهد ارسالی، در انتظار داوری','approved'=>'تأیید مدیر','rejected'=>'ردشده؛ نیازمند اصلاح'];
    echo '<p class="muted">کیفیت: '.esc($states[$plan['review_state']]??$plan['review_state']).' | ریسک: '.esc($plan['risk']).'</p>';
    echo '<details><summary>برنامه و مدارک</summary><p>'.esc($plan['deliverable']).'</p><p>'.esc($plan['acceptance']).'</p>';
    if($plan['evidence_url']!=='')echo '<p>مرجع شواهد: '.esc($plan['evidence_url']).'</p>';
    if($t['state']==='in_progress'&&in_array($plan['review_state'],['planned','rejected'],true)){
        formBegin('cc_evidence');echo '<input type="hidden" name="task_id" value="'.$id.'">';
        echo '<label>پیوند HTTPS شواهد (بدون اطلاعات ورود)</label><input type="url" name="evidence_url" maxlength="500" required>';
        echo '<button>ارسال برای بررسی</button></form>';
    }
    if($t['state']==='in_progress'&&$plan['review_state']==='submitted'){
        formBegin('cc_review');echo '<input type="hidden" name="task_id" value="'.$id.'">';
        echo '<label>تصمیم مدیر</label><select name="decision"><option value="reject">رد و درخواست اصلاح</option><option value="approve">تأیید پس از بررسی مدارک</option></select>';
        echo '<label>توضیح و مبنای تصمیم</label><input name="review_note" maxlength="1000" required>';
        echo '<button>ثبت داوری</button></form>';
    }
    echo '</details>';
}

<?php
declare(strict_types=1);
/** Owner-only private treasury proposal user interface; never triggers a bank transfer. */
function zmTreasuryUiHandle(PDO $db,string $action):void {
    authorize('manage');
    if(!in_array(role(),['admin','manager','accountant'],true))
        bail('Treasury role unavailable',403);
    if($action==='treasury_create'){
        zmTreasuryNew($db,req('request_key'),req('reference'),req('purpose'),
            req('direction','payable'),cents(req('amount')),req('currency','IRR'),actor(),role());
    }elseif($action==='treasury_decision'){
        zmTreasuryDecide($db,(int)req('treasury_id'),req('decision'),req('reason'),actor(),role());
    }else bail('Unsupported treasury operation',403);
}
function zmTreasuryUiRender(PDO $db):void {
    authorize('view');
    $states=['draft'=>'پیش‌نویس','submitted'=>'در انتظار بررسی','approved'=>'تأیید داخلی','rejected'=>'ردشده','cancelled'=>'لغوشده'];
    echo '<section><h2>خزانه‌داری — درخواست‌های داخلی پرداخت و دریافت</h2>';
    echo '<p class="muted">این ماژول هیچ پرداخت، برداشت، صدور سند حسابداری یا اتصال به بانک انجام نمی‌دهد. تأیید مدیر تنها یک مجوز داخلی برای مراحل قانونی بعدی است.</p></section>';
    if(in_array(role(),['admin','manager','accountant'],true)){
        echo '<section><h2>ثبت درخواست جدید</h2>';
        formBegin('treasury_create');
        echo '<input type="hidden" name="request_key" value="'.bin2hex(random_bytes(16)).'">';
        echo '<label>شماره مرجع یا فاکتور</label><input name="reference" maxlength="100" required>';
        echo '<label>شرح و هدف</label><textarea name="purpose" maxlength="750" required></textarea>';
        echo '<label>نوع</label><select name="direction"><option value="payable">پرداخت پیشنهادی</option><option value="receivable">دریافت پیشنهادی</option></select>';
        echo '<label>مبلغ</label><input name="amount" required inputmode="decimal" placeholder="15000.00">';
        echo '<label>ارز</label><select name="currency"><option>IRR</option><option>USD</option><option>EUR</option><option>AED</option></select>';
        echo '<button>ثبت پیش‌نویس بدون پرداخت</button></form></section>';
    }
    echo '<section><h2>صف درخواست‌ها</h2><div class="scroll"><table><thead><tr><th>شناسه</th><th>مرجع</th><th>شرح</th><th>مبلغ</th><th>وضعیت</th><th>ثبت تصمیم</th></tr></thead><tbody>';
    foreach(q($db,'SELECT * FROM treasury_requests ORDER BY id DESC LIMIT 100') as $row){
        $id=(int)$row['id'];
        echo '<tr><td>'.$id.'</td><td>'.esc($row['reference']).'</td><td>'.esc($row['purpose']).'</td>';
        echo '<td>'.money((int)$row['amount_minor']).' '.esc($row['currency']).'</td><td>'.esc($states[$row['status']]??$row['status']).'</td><td>';
        $options=[];
        if(in_array(role(),['admin','manager','accountant'],true)){
            if($row['status']==='draft'&&((int)$row['requested_by']===actor()||role()==='admin'))
                $options=['submit'=>'ارسال','cancel'=>'لغو'];
            if($row['status']==='submitted'&&role()==='admin'&&(int)$row['requested_by']!==actor())
                $options=['approve'=>'تأیید داخلی','reject'=>'رد'];
        }
        if($options){
            formBegin('treasury_decision');
            echo '<input type="hidden" name="treasury_id" value="'.$id.'"><select name="decision">';
            foreach($options as $value=>$label)echo '<option value="'.esc($value).'">'.esc($label).'</option>';
            echo '</select><input name="reason" maxlength="700" required placeholder="دلیل بررسی">';
            echo '<button>ثبت تصمیم</button></form>';
        }
        echo '</td></tr>';
    }
    echo '</tbody></table></div></section>';
    $findings=zmTreasuryAudit($db);
    echo '<section><h2>کنترل سوابق</h2>';
    if(!$findings)echo '<p>در گردش‌کار ثبت‌شده مغایرت ساختاری شناسایی نشد.</p>';
    else foreach($findings as $finding)
        echo '<p class="notice">'.esc($finding['code']).' #'.(int)$finding['request'].'</p>';
    echo '</section>';
}

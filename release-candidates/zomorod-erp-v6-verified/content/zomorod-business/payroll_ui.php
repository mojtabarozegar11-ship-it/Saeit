<?php
declare(strict_types=1);
/** HTML controller of internal payroll proposals, private authenticated app only. */
function zmPayrollUiHandle(PDO $db,string $action):void {
    authorize('manage');
    if(!in_array(role(),['admin','manager','accountant'],true))
        bail('امکان ثبت درخواست حقوق برای این نقش وجود ندارد.',403);
    if($action==='payroll_create'){
        $lines=[];
        for($i=0;$i<8;$i++){
            $ref=req('employee_'.$i);
            if($ref==='')continue;
            $lines[]=[
                'employee_ref'=>$ref,
                'base'=>cents(req('base_'.$i,'0')),
                'addition'=>cents(req('addition_'.$i,'0')),
                'deduction'=>cents(req('deduction_'.$i,'0')),
            ];
        }
        zmPayrollCreate($db,req('request_key'),req('period'),req('currency','IRR'),$lines,actor());
    }elseif($action==='payroll_decision'){
        zmPayrollDecision($db,(int)req('period_id'),req('decision'),actor(),role(),req('reason'));
    }else bail('عملیات حقوق نامعتبر است.',403);
}
function zmPayrollUiRender(PDO $db):void {
    authorize('view');
    $states=['draft'=>'پیش‌نویس','submitted'=>'منتظر بررسی','approved'=>'تأیید داخلی','rejected'=>'ردشده','cancelled'=>'لغوشده'];
    echo '<section><h2>محاسبهٔ پیشنهادی حقوق و دستمزد</h2><p class="muted">این صفحه فقط برای گردآوری و تأیید داخلی ارقام است؛ پرداخت حقوق، مالیات و بیمه را محاسبه یا ارسال نمی‌کند. ارقام باید پیش از استفادهٔ واقعی توسط مسئول مالی بررسی شوند.</p></section>';
    if(in_array(role(),['admin','manager','accountant'],true)){
        echo '<section><h2>ثبت پروندهٔ پیشنهادی یک ماه</h2>';
        formBegin('payroll_create');
        echo '<input type="hidden" name="request_key" value="'.bin2hex(random_bytes(16)).'">';
        echo '<label>دورهٔ میلادی</label><input name="period" pattern="20[0-9]{2}-(0[1-9]|1[0-2])" placeholder="2026-10" required maxlength="7">';
        echo '<label>ارز</label><select name="currency"><option>IRR</option><option>USD</option><option>EUR</option><option>AED</option></select>';
        echo '<p class="muted">مبالغ برحسب واحد اصلی ارز، مانند 1500.00. در این فرم حداکثر ۸ نفر ثبت می‌شوند.</p>';
        echo '<div class="scroll"><table><tr><th>کد کارمند</th><th>حقوق پایه</th><th>اضافات</th><th>کسورات</th></tr>';
        for($i=0;$i<8;$i++){
            echo '<tr><td><input name="employee_'.$i.'" maxlength="32" placeholder="EMP001"></td>';
            foreach(['base','addition','deduction'] as $name)
                echo '<td><input name="'.$name.'_'.$i.'" inputmode="decimal" value="0"></td>';
            echo '</tr>';
        }
        echo '</table></div><button>ثبت پروندهٔ پیشنهادی</button></form></section>';
    }
    echo '<section><h2>دوره‌ها و نظارت</h2><div class="scroll"><table>';
    echo '<tr><th>دوره</th><th>وضعیت</th><th>ناخالص</th><th>کسورات</th><th>خالص</th><th>عملیات</th></tr>';
    foreach(q($db,'SELECT * FROM payroll_periods ORDER BY period DESC LIMIT 50') as $p){
        echo '<tr><td>'.esc($p['period']).'</td><td>'.esc($states[$p['state']]??$p['state']).'</td>';
        echo '<td>'.money((int)$p['gross_total']).' '.esc($p['currency']).'</td>';
        echo '<td>'.money((int)$p['deduction_total']).'</td><td>'.money((int)$p['net_total']).'</td><td>';
        $options=[];
        if($p['state']==='draft'&&((int)$p['requested_by']===actor()||role()==='admin'))
            $options=['submit'=>'ارسال برای بررسی','cancel'=>'لغو'];
        if($p['state']==='submitted'&&role()==='admin'&&(int)$p['requested_by']!==actor())
            $options=['approve'=>'تأیید مدیر مستقل','reject'=>'رد'];
        if($options){
            formBegin('payroll_decision');
            echo '<input type="hidden" name="period_id" value="'.(int)$p['id'].'"><select name="decision">';
            foreach($options as $name=>$label)echo '<option value="'.esc($name).'">'.esc($label).'</option>';
            echo '</select><input name="reason" maxlength="900" required placeholder="دلیل مستند تصمیم"><button>ثبت تصمیم</button></form>';
        }
        echo '</td></tr>';
    }
    echo '</table></div></section>';
    echo '<section><h2>بازبینی کنترل توازن</h2>';
    $findings=zmPayrollAudit($db);
    if(!$findings)echo '<p>در پرونده‌های ثبت‌شده مغایرت جمع گزارش نشد؛ این تأیید صحت قرارداد یا محاسبات قانونی نیست.</p>';
    else foreach($findings as $r)echo '<p class="notice">'.(int)$r['period_id'].' / '.esc($r['code']).'</p>';
    echo '</section>';
}

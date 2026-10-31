<?php
declare(strict_types=1);
/**
 * Strictly read-only independent accounting controls. Findings are alerts, not
 * an audit opinion or tax compliance certificate. Never adjusts journal entries.
 */
function zmFinanceAudit(PDO $db): array {
    $check=$db->query('PRAGMA integrity_check')->fetchColumn();
    $foreign=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_NUM);
    $unbalanced=(int)$db->query("SELECT COUNT(*) FROM (
        SELECT entry_id,currency,SUM(debit) debit,SUM(credit) credit
        FROM journal_lines GROUP BY entry_id,currency
        HAVING SUM(debit)<>SUM(credit) OR SUM(debit)=0
    )")->fetchColumn();
    $shortEntries=(int)$db->query("SELECT COUNT(*) FROM (
        SELECT e.id FROM journal_entries e LEFT JOIN journal_lines l ON l.entry_id=e.id
        GROUP BY e.id HAVING COUNT(l.id)<2
    )")->fetchColumn();
    $overpaid=(int)$db->query("SELECT COUNT(*) FROM invoices i WHERE
        COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0)>i.amount")->fetchColumn();
    $negativeStock=(int)$db->query("SELECT COUNT(*) FROM (
        SELECT i.id FROM inventory i LEFT JOIN inventory_movements m ON m.inventory_id=i.id
        GROUP BY i.id HAVING COALESCE(SUM(m.qty),0)<0
    )")->fetchColumn();
    // An invoice and/or payment must never point at the same posting as
    // another commercial document, even when the posting balances.
    $postingReuse=(int)$db->query("SELECT COUNT(*) FROM (
        SELECT posting_id FROM (
            SELECT posted_entry AS posting_id FROM invoices
            UNION ALL SELECT entry_id AS posting_id FROM invoice_payments
        ) WHERE posting_id IS NOT NULL GROUP BY posting_id HAVING COUNT(*)>1
    )")->fetchColumn();
    // Read in sequence using a cursor; later receipts must not conceal an
    // earlier negative stock position. Stream rows: O(n) time, O(1) state.
    $historicalNegative=0;$lastId=null;$running=0;$seenNegative=false;
    $moves=$db->query('SELECT inventory_id,qty FROM inventory_movements ORDER BY inventory_id,movement_date,id');
    while(($move=$moves->fetch(PDO::FETCH_ASSOC))!==false){
        $id=(int)$move['inventory_id'];
        if($lastId!==$id){$lastId=$id;$running=0;$seenNegative=false;}
        $running+=(int)$move['qty'];
        if($running<0 && !$seenNegative){$historicalNegative++;$seenNegative=true;}
    }
    $balances=$db->query("SELECT currency,SUM(debit) total_dr,SUM(credit) total_cr
        FROM journal_lines GROUP BY currency ORDER BY currency")->fetchAll(PDO::FETCH_ASSOC);
    $imbalancedCurrencies=0;
    foreach($balances as $line)if((int)$line['total_dr']!==(int)$line['total_cr'])$imbalancedCurrencies++;
    $issues=[
        'integrity'=>$check==='ok'?0:1,
        'foreign_keys'=>count($foreign),
        'entry_currency_balance'=>$unbalanced,
        'entries_under_two_lines'=>$shortEntries,
        'invoice_overpayment'=>$overpaid,
        'negative_stock'=>$negativeStock,
        'posting_reuse'=>$postingReuse,
        'historical_negative_stock'=>$historicalNegative,
        'currency_balance'=>$imbalancedCurrencies,
    ];
    $result='CLEAR_ON_CHECKED_INVARIANTS';
    if(array_sum($issues)>0)$result='REQUIRES_INVESTIGATION';
    return ['result'=>$result,'checks'=>$issues,'balances'=>$balances,'scanned_at'=>gmdate('Y-m-d H:i:s').' UTC'];
}
function zmFinanceAuditRender(PDO $db): void {
    authorize('account');
    $audit=zmFinanceAudit($db);
    echo '<section><h2>ممیزی مستقل و فقط‌خواندنی حسابداری</h2><p class="muted">این گزارش فقط ناسازگاری‌های داخلی قابل اندازه‌گیری را بررسی می‌کند و جایگزین حسابرسی رسمی، مقررات مالیاتی یا کنترل بانکی نیست. هیچ داده‌ای اصلاح نمی‌شود.</p>';
    echo '<p><strong>وضعیت کنترل‌های بررسی‌شده: '.esc($audit['result']).'</strong></p>';
    $labels=[
        'integrity'=>'سلامت ساختار SQLite',
        'foreign_keys'=>'رکوردهای با ارجاع نامعتبر',
        'entry_currency_balance'=>'اسناد نامتوازن به تفکیک ارز',
        'entries_under_two_lines'=>'اسناد با کمتر از دو ردیف',
        'invoice_overpayment'=>'فاکتورهای دارای ثبت تسویه بیش از مبلغ',
        'negative_stock'=>'کالاهای با موجودی منفی',
        'posting_reuse'=>'ارجاعات تکراری به اسناد مالی',
        'historical_negative_stock'=>'کالاهای دارای سابقهٔ موجودی منفی',
        'currency_balance'=>'ارزهای دارای اختلاف بدهکار و بستانکار',
    ];
    echo '<div class="grid">';
    foreach($audit['checks'] as $key=>$n)echo '<div class="card"><div class="metric">'.(int)$n.'</div>'.esc($labels[$key]??$key).'</div>';
    echo '</div><p class="muted">زمان بررسی: '.esc($audit['scanned_at']).'</p></section>';
    echo '<section><h2>کنترل توازن کل حساب‌ها بر اساس ارز</h2><div class="scroll"><table><tr><th>ارز</th><th>بدهکار</th><th>بستانکار</th><th>اختلاف</th></tr>';
    foreach($audit['balances'] as $b){
        $dr=(int)$b['total_dr'];$cr=(int)$b['total_cr'];
        echo '<tr><td>'.esc($b['currency']).'</td><td>'.money($dr).'</td><td>'.money($cr).'</td><td>'.money($dr-$cr).'</td></tr>';
    }
    echo '</table></div></section>';
}

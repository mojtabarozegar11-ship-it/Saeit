<?php
declare(strict_types=1);
/**
 * Read-only, authenticated executive overview.
 * This file belongs OUTSIDE public_html. Never opens another site's database.
 * No schema changes, no writes, and no bank/payment integrations.
 */
if (!isset($db) || !($db instanceof PDO) || !function_exists('actor') || actor() <= 0) {
    http_response_code(403);
    exit;
}
authorize('view');

$from = (string)($_GET['from'] ?? gmdate('Y-m-01'));
$to = (string)($_GET['to'] ?? gmdate('Y-m-d'));
$kind = (string)($_GET['kind'] ?? 'all');
$currency = (string)($_GET['currency'] ?? 'all');
$term = trim((string)($_GET['term'] ?? ''));
if (!validDate($from) || !validDate($to) || $from > $to ||
    !in_array($kind, ['all', 'sale', 'purchase'], true) ||
    !in_array($currency, ['all', 'IRR', 'USD', 'EUR', 'AED'], true) ||
    strlen($term) > 80) {
    bail('بازه زمانی یا فیلتر گزارش معتبر نیست.', 422);
}
$where = ['i.invoice_date >= ?', 'i.invoice_date <= ?'];
$params = [$from, $to];
if ($kind !== 'all') { $where[] = 'i.kind = ?'; $params[] = $kind; }
if ($currency !== 'all') { $where[] = 'i.currency = ?'; $params[] = $currency; }
if ($term !== '') {
    // instr() treats percent and underscore as literals, not SQL LIKE wildcards.
    $where[] = '(instr(i.invoice_no, ?) > 0 OR instr(p.name, ?) > 0)';
    $params[] = $term;
    $params[] = $term;
}
$filter = implode(' AND ', $where);
$paidJoin = ' LEFT JOIN (SELECT invoice_id,SUM(amount) paid FROM invoice_payments GROUP BY invoice_id) ip ON ip.invoice_id=i.id ';
$partyJoin = ' JOIN parties p ON p.id=i.party_id ';

$summary = q($db,
    'SELECT i.kind,i.currency,COUNT(*) invoices,SUM(i.amount) total,SUM(COALESCE(ip.paid,0)) paid ' .
    'FROM invoices i ' . $partyJoin . $paidJoin . ' WHERE ' . $filter .
    ' GROUP BY i.kind,i.currency ORDER BY i.currency,i.kind', $params);
$invoices = q($db,
    'SELECT i.invoice_no,i.kind,i.invoice_date,i.due_date,i.amount,i.currency,p.name party, ' .
    'COALESCE(ip.paid,0) paid FROM invoices i ' . $partyJoin . $paidJoin .
    ' WHERE ' . $filter . ' ORDER BY i.invoice_date DESC,i.id DESC LIMIT 60', $params);

$today = gmdate('Y-m-d');
$overdue = q($db,
    'SELECT i.invoice_no,i.kind,i.due_date,i.amount,i.currency,p.name party,COALESCE(ip.paid,0) paid ' .
    'FROM invoices i ' . $partyJoin . $paidJoin .
    ' WHERE i.due_date < ? AND i.amount > COALESCE(ip.paid,0) ' .
    'ORDER BY i.due_date ASC,i.id ASC LIMIT 40', [$today]);
$overdueCounts = q($db,
    'SELECT i.kind,i.currency,COUNT(*) invoices,SUM(i.amount-COALESCE(ip.paid,0)) outstanding ' .
    'FROM invoices i ' . $paidJoin .
    ' WHERE i.due_date < ? AND i.amount > COALESCE(ip.paid,0) ' .
    'GROUP BY i.kind,i.currency ORDER BY i.currency,i.kind', [$today]);
$stock = q($db,
    'SELECT i.sku,i.name,i.unit,i.reorder_level,COALESCE(SUM(m.qty),0) stock ' .
    'FROM inventory i LEFT JOIN inventory_movements m ON m.inventory_id=i.id ' .
    'WHERE i.reorder_level > 0 GROUP BY i.id ' .
    'HAVING COALESCE(SUM(m.qty),0) <= i.reorder_level ' .
    'ORDER BY stock ASC,i.name LIMIT 40');
$projects = q($db,
    'SELECT state,COUNT(*) projects,COALESCE(SUM(budget),0) budget ' .
    'FROM projects GROUP BY state ORDER BY state');
$kpis = [
    'طرف‌های حساب' => (int)one($db, 'SELECT COUNT(*) FROM parties'),
    'فاکتورهای ثبت‌شده' => (int)one($db, 'SELECT COUNT(*) FROM invoices'),
    'اسناد مالی' => (int)one($db, 'SELECT COUNT(*) FROM journal_entries'),
    'پرسنل فعال' => (int)one($db, 'SELECT COUNT(*) FROM employees WHERE active=1'),
    'پروژه‌های فعال' => (int)one($db, "SELECT COUNT(*) FROM projects WHERE state='active'"),
    'هشدار موجودی' => count($stock),
];
echo '<style>.zm-insights-filter{display:flex;align-items:end;flex-wrap:wrap;gap:12px}.zm-insights-filter label{flex:1 1 145px}.zm-insights-filter input,.zm-insights-filter select{width:100%;max-width:none}.zm-insights-actions{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.zm-insights-actions a{padding:9px 13px;border:1px solid #ae9354;border-radius:12px;background:#233b29}.zm-insights-stat{font-variant-numeric:tabular-nums}.zm-insights-note{font-size:13px;color:#ccd3be}.zm-insights-empty{padding:12px;color:#cbd3c1}.zm-insights-date{direction:ltr;unicode-bidi:isolate;display:inline-block}</style>';
echo '<section><h2>مرکز گزارش و کنترل مدیریتی</h2><p class="zm-insights-note">این نمای مدیریتی فقط اطلاعات ثبت‌شده در همین سامانه را نمایش می‌دهد. مبلغ ارزهای مختلف با یکدیگر جمع نمی‌شود. هیچ تراکنش واقعی بانکی انجام نمی‌گیرد.</p>';
echo '<div class="zm-insights-actions"><a href="?page=invoices">ثبت و بررسی فاکتور</a><a href="?page=payments">دریافت و پرداخت</a><a href="?page=inventory">کنترل انبار</a><a href="?page=projects">پروژه‌ها</a><a href="?page=trial">تراز و سود و زیان</a></div>';
echo '<form method="get" class="zm-insights-filter" autocomplete="off"><input type="hidden" name="page" value="insights">';
echo '<label>از تاریخ <input name="from" type="date" required value="'.esc($from).'"></label>';
echo '<label>تا تاریخ <input name="to" type="date" required value="'.esc($to).'"></label>';
echo '<label>نوع فاکتور<select name="kind"><option value="all">همه</option>';
foreach (['sale'=>'فروش','purchase'=>'خرید'] as $v=>$label) echo '<option value="'.esc($v).'"'.($kind===$v?' selected':'').'>'.esc($label).'</option>';
echo '</select></label><label>ارز<select name="currency"><option value="all">همه ارزها</option>';
foreach (['IRR','USD','EUR','AED'] as $v) echo '<option value="'.esc($v).'"'.($currency===$v?' selected':'').'>'.esc($v).'</option>';
echo '</select></label><label>جست‌وجوی شماره یا طرف‌حساب<input name="term" maxlength="80" value="'.esc($term).'" placeholder="شماره فاکتور یا نام"></label><button type="submit">نمایش گزارش</button></form>';
echo '<p class="zm-insights-note">دوره انتخابی: <span class="zm-insights-date">'.esc($from).' — '.esc($to).'</span>. گزارش سررسیدگذشته و هشدار موجودی مستقل از بازهٔ انتخابی و مربوط به وضعیت کل سامانه هستند.</p></section>';
echo '<div class="grid">';
foreach ($kpis as $label=>$value) {
    echo '<div class="card"><div class="metric zm-insights-stat">'.esc($value).'</div><h3>'.esc($label).'</h3></div>';
}
echo '</div>';
echo '<section><h2>خلاصه فاکتورهای دوره به تفکیک ارز و نوع</h2><div class="scroll"><table><thead><tr><th>نوع</th><th>ارز</th><th>تعداد</th><th>جمع مبلغ</th><th>تسویه‌شده</th><th>باقیمانده</th></tr></thead><tbody>';
foreach ($summary as $r) echo '<tr><td>'.($r['kind']==='sale'?'فروش':'خرید').'</td><td>'.esc($r['currency']).'</td><td>'.(int)$r['invoices'].'</td><td>'.money((int)$r['total']).'</td><td>'.money((int)$r['paid']).'</td><td>'.money((int)$r['total']-(int)$r['paid']).'</td></tr>';
if (!$summary) echo '<tr><td colspan="6" class="zm-insights-empty">در این بازه و با این فیلتر، فاکتوری ثبت نشده است.</td></tr>';
echo '</tbody></table></div></section>';
echo '<section><h2>فاکتورهای مطابق فیلتر (۶۰ مورد آخر)</h2><div class="scroll"><table><thead><tr><th>شماره</th><th>نوع</th><th>طرف حساب</th><th>تاریخ</th><th>سررسید</th><th>ارز</th><th>مبلغ</th><th>مانده</th></tr></thead><tbody>';
foreach ($invoices as $r) echo '<tr><td>'.esc($r['invoice_no']).'</td><td>'.($r['kind']==='sale'?'فروش':'خرید').'</td><td>'.esc($r['party']).'</td><td>'.esc($r['invoice_date']).'</td><td>'.esc($r['due_date']).'</td><td>'.esc($r['currency']).'</td><td>'.money((int)$r['amount']).'</td><td>'.money((int)$r['amount']-(int)$r['paid']).'</td></tr>';
if (!$invoices) echo '<tr><td colspan="8" class="zm-insights-empty">نتیجه‌ای پیدا نشد.</td></tr>';
echo '</tbody></table></div></section>';
echo '<section><h2>مطالبات و بدهی‌های سررسیدگذشته (کل سوابق)</h2><div class="scroll"><table><thead><tr><th>نوع</th><th>ارز</th><th>تعداد</th><th>مانده سررسیدگذشته</th></tr></thead><tbody>';
foreach ($overdueCounts as $r) echo '<tr><td>'.($r['kind']==='sale'?'مطالبات فروش':'بدهی خرید').'</td><td>'.esc($r['currency']).'</td><td>'.(int)$r['invoices'].'</td><td>'.money((int)$r['outstanding']).'</td></tr>';
if (!$overdueCounts) echo '<tr><td colspan="4" class="zm-insights-empty">ماندهٔ سررسیدگذشته‌ای ثبت نشده است.</td></tr>';
echo '</tbody></table></div><h3>قدیمی‌ترین سررسیدها (حداکثر ۴۰)</h3><div class="scroll"><table><thead><tr><th>فاکتور</th><th>طرف حساب</th><th>سررسید</th><th>نوع</th><th>ارز</th><th>مانده</th></tr></thead><tbody>';
foreach ($overdue as $r) echo '<tr><td>'.esc($r['invoice_no']).'</td><td>'.esc($r['party']).'</td><td>'.esc($r['due_date']).'</td><td>'.($r['kind']==='sale'?'مطالبه':'بدهی').'</td><td>'.esc($r['currency']).'</td><td>'.money((int)$r['amount']-(int)$r['paid']).'</td></tr>';
if (!$overdue) echo '<tr><td colspan="6" class="zm-insights-empty">مورد معوق ثبت نشده است.</td></tr>';
echo '</tbody></table></div></section>';
echo '<section><h2>هشدار موجودی انبار (نقطه سفارش تعریف‌شده)</h2><div class="scroll"><table><thead><tr><th>کد</th><th>کالا</th><th>موجودی</th><th>حد سفارش</th><th>واحد</th></tr></thead><tbody>';
foreach ($stock as $r) echo '<tr><td>'.esc($r['sku']).'</td><td>'.esc($r['name']).'</td><td>'.(int)$r['stock'].'</td><td>'.(int)$r['reorder_level'].'</td><td>'.esc($r['unit']).'</td></tr>';
if (!$stock) echo '<tr><td colspan="5" class="zm-insights-empty">کمبود زیر نقطه سفارش ثبت نشده است؛ کالاهای بدون نقطه سفارش پایش نمی‌شوند.</td></tr>';
echo '</tbody></table></div></section>';
echo '<section><h2>ترکیب و بودجه ثبت‌شدهٔ پروژه‌ها</h2><div class="scroll"><table><thead><tr><th>وضعیت</th><th>تعداد</th><th>جمع بودجه (IRR)</th></tr></thead><tbody>';
foreach ($projects as $r) {
    $states=['planned'=>'برنامه‌ریزی','active'=>'فعال','paused'=>'متوقف','done'=>'پایان‌یافته'];
    echo '<tr><td>'.esc($states[$r['state']] ?? $r['state']).'</td><td>'.(int)$r['projects'].'</td><td>'.money((int)$r['budget']).'</td></tr>';
}
if (!$projects) echo '<tr><td colspan="3" class="zm-insights-empty">پروژه‌ای ثبت نشده است.</td></tr>';
echo '</tbody></table></div></section>';

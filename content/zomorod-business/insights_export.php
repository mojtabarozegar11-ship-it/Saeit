<?php
declare(strict_types=1);
/** Private, authenticated, read-only export for the isolated management database. */
if (!isset($db) || !($db instanceof PDO) || !function_exists('actor') || actor() <= 0) {
    http_response_code(403);
    exit;
}
authorize('view');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') bail('فقط دریافت گزارش مجاز است.', 405);
$report = (string)($_GET['report'] ?? '');
if (!in_array($report, ['invoices', 'overdue', 'stock', 'projects'], true)) {
    bail('نوع گزارش معتبر نیست.', 422);
}
function zmCsvSafe(mixed $value): string {
    $cell = (string)$value;
    // Spreadsheet formula injection: text imported in Excel/Calc must never execute.
    if (preg_match('/^[\x00-\x20\x{FEFF}]*[=+\-@]/u', $cell) === 1) {
        return "'".$cell;
    }
    return $cell;
}
$limit = 3001;
$columns = [];
$rows = [];
if ($report === 'invoices') {
    $from = (string)($_GET['from'] ?? gmdate('Y-m-01'));
    $to = (string)($_GET['to'] ?? gmdate('Y-m-d'));
    $kind = (string)($_GET['kind'] ?? 'all');
    $currency = (string)($_GET['currency'] ?? 'all');
    $term = trim((string)($_GET['term'] ?? ''));
    if (!validDate($from) || !validDate($to) || $from > $to ||
        !in_array($kind, ['all', 'sale', 'purchase'], true) ||
        !in_array($currency, ['all', 'IRR', 'USD', 'EUR', 'AED'], true) ||
        strlen($term) > 80) {
        bail('بازه زمانی یا فیلتر گزارش نامعتبر است.', 422);
    }
    $where = ['i.invoice_date >= ?', 'i.invoice_date <= ?'];
    $params = [$from, $to];
    if ($kind !== 'all') { $where[] = 'i.kind = ?'; $params[] = $kind; }
    if ($currency !== 'all') { $where[] = 'i.currency = ?'; $params[] = $currency; }
    if ($term !== '') {
        $where[] = '(instr(i.invoice_no, ?) > 0 OR instr(p.name, ?) > 0)';
        $params[] = $term;
        $params[] = $term;
    }
    $columns = ['شماره فاکتور','نوع','طرف حساب','تاریخ','سررسید','ارز','مبلغ','تسویه‌شده','باقیمانده'];
    $query = 'SELECT i.invoice_no,i.kind,p.name AS party,i.invoice_date,i.due_date,i.currency,' .
             'i.amount,COALESCE(ip.paid,0) paid FROM invoices i ' .
             'JOIN parties p ON p.id=i.party_id ' .
             'LEFT JOIN (SELECT invoice_id,SUM(amount) paid FROM invoice_payments GROUP BY invoice_id) ip ON ip.invoice_id=i.id ' .
             'WHERE '.implode(' AND ', $where).' ORDER BY i.invoice_date DESC,i.id DESC LIMIT '.$limit;
    foreach (q($db, $query, $params) as $item) {
        $rows[] = [
            $item['invoice_no'], $item['kind']==='sale'?'فروش':'خرید',
            $item['party'], $item['invoice_date'], $item['due_date'], $item['currency'],
            money((int)$item['amount']), money((int)$item['paid']),
            money((int)$item['amount']-(int)$item['paid'])
        ];
    }
} elseif ($report === 'overdue') {
    $columns = ['شماره فاکتور','نوع','طرف حساب','سررسید','ارز','مانده'];
    $sql = 'SELECT i.invoice_no,i.kind,p.name AS party,i.due_date,i.currency,i.amount,COALESCE(ip.paid,0) paid ' .
           'FROM invoices i JOIN parties p ON p.id=i.party_id ' .
           'LEFT JOIN (SELECT invoice_id,SUM(amount) paid FROM invoice_payments GROUP BY invoice_id) ip ON ip.invoice_id=i.id ' .
           'WHERE i.due_date < ? AND i.amount > COALESCE(ip.paid,0) ORDER BY i.due_date,i.id LIMIT '.$limit;
    foreach (q($db, $sql, [gmdate('Y-m-d')]) as $item) {
        $rows[] = [$item['invoice_no'], $item['kind']==='sale'?'مطالبه':'بدهی',
          $item['party'], $item['due_date'], $item['currency'], money((int)$item['amount']-(int)$item['paid'])];
    }
} elseif ($report === 'stock') {
    $columns = ['شناسه کالا','کالا','موجودی','نقطه سفارش','واحد'];
    $sql = 'SELECT i.sku,i.name,i.unit,i.reorder_level,COALESCE(SUM(m.qty),0) stock FROM inventory i ' .
           'LEFT JOIN inventory_movements m ON m.inventory_id=i.id ' .
           'WHERE i.reorder_level > 0 GROUP BY i.id HAVING COALESCE(SUM(m.qty),0) <= i.reorder_level ' .
           'ORDER BY stock,i.name LIMIT '.$limit;
    foreach (q($db, $sql) as $item) {
        $rows[] = [$item['sku'], $item['name'], (int)$item['stock'], (int)$item['reorder_level'], $item['unit']];
    }
} else {
    $columns = ['عنوان پروژه','مسئول','وضعیت','بودجه ثبت‌شده IRR'];
    foreach (q($db, 'SELECT title,owner,state,budget FROM projects ORDER BY id DESC LIMIT '.$limit) as $item) {
        $states=['planned'=>'برنامه‌ریزی','active'=>'فعال','paused'=>'متوقف','done'=>'خاتمه‌یافته'];
        $rows[] = [$item['title'], $item['owner'], $states[$item['state']]??$item['state'], money((int)$item['budget'])];
    }
}
if (count($rows) >= $limit) bail('حجم گزارش از ۳۰۰۰ ردیف بیشتر است؛ بازه را محدود کنید.', 422);
header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="zomorod-business-'.$report.'-'.gmdate('Ymd').'.csv"');
header('Cache-Control: private, no-store, max-age=0');
header('X-Content-Type-Options: nosniff');
$stream = fopen('php://output', 'wb');
if ($stream === false) throw new RuntimeException('CSV output unavailable');
fwrite($stream, "\xEF\xBB\xBF");
fputcsv($stream, array_map('zmCsvSafe', $columns), ',', '"', '');
foreach ($rows as $row) {
    fputcsv($stream, array_map('zmCsvSafe', $row), ',', '"', '');
}
fclose($stream);

<?php
declare(strict_types=1);
/**
 * Read-only bridges from private workflow/store/customer databases to the owner task queue.
 * The only writes are idempotent tasks and task_events in command-center.sqlite3.
 * Never creates invoices, confirms settlements, changes products or grants approvals.
 */

function zmCcBridgeReadOnly(string $file): ?PDO {
    if (!is_file($file)) return null;
    if (is_link($file) || !is_readable($file)) {
        throw new RuntimeException('Unsafe or unreadable integration database');
    }
    $db = new PDO('sqlite:'.$file, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 10,
    ]);
    $db->exec('PRAGMA query_only=ON; PRAGMA busy_timeout=10000;');
    return $db;
}

function zmCcScanBridges(PDO $control, int $uid, ?string $private=null): array {
    $private = $private ?? __DIR__;
    if (!is_dir($private) || is_link($private)) {
        throw new RuntimeException('Private integration directory unavailable');
    }
    $created = 0;
    $inspected = 0;
    $sources = [];
    $queue = static function(string $source, string $stream, string $title,
                            string $detail, string $priority) use ($control, $uid, &$created, &$sources): void {
        $key = substr(hash('sha256', 'zm-cc-bridge-v1:'.$source), 0, 32);
        if (zmCcCreate($control, $key, $source, $stream, $title, $detail, $priority, $uid)) {
            ++$created;
            $sources[] = $source;
        }
    };

    // Independent finance queue: unverified operator declarations must never
    // be promoted to paid invoices or accounting entries by a scanner.
    $bankClaims = zmCcBridgeReadOnly($private.'/management.sqlite3');
    if ($bankClaims !== null) {
        $available = (int)$bankClaims->query("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='bank_receipt_claims'")->fetchColumn();
        if ($available) {
            $pending = $bankClaims->query("SELECT id FROM bank_receipt_claims WHERE status='pending' ORDER BY id DESC LIMIT 30")->fetchAll();
            foreach ($pending as $item) {
                ++$inspected;
                $claimId = (int)$item['id'];
                if ($claimId<1) continue;
                $queue('bank:unverified-claim:'.$claimId, 'finance',
                    'بررسی اظهار بانکی تأییدنشده شماره '.$claimId,
                    'درخواست بررسی در /business/banking.php؛ این اظهار، دلیل وصول واقعی، تسویه فاکتور یا اجازه تحویل نیست. تأیید فقط با استعلام مستقل بانک و روال کنترل‌شده امکان‌پذیر است.',
                    'high');
            }
        }
    }

    $flow = zmCcBridgeReadOnly($private.'/company-workflow.sqlite3');
    if ($flow !== null) {
        $items = $flow->query("SELECT id,category,risk FROM requests WHERE state='submitted' ORDER BY id DESC LIMIT 30")->fetchAll();
        foreach ($items as $r) {
            ++$inspected;
            $id = (int)$r['id'];
            $risk = (string)$r['risk'];
            $queue('workflow:'.$id, 'operations', 'تصمیم‌گیری درباره درخواست سازمانی شماره '.$id,
                'درخواست در کارتابل منتظر بررسی است. نوع: '.(string)$r['category'].
                '؛ ریسک: '.$risk.'؛ مسیر پیگیری: /business/?page=workflow_desk. تأیید این وظیفه به‌معنای تصویب درخواست نیست.',
                $risk==='high_impact' ? 'critical' : 'high');
        }
    }

    $store = zmCcBridgeReadOnly($private.'/site_store.sqlite3');
    if ($store !== null) {
        $payment = $store->query('SELECT provider,state FROM payment_state WHERE id=1')->fetch();
        if ($payment) {
            ++$inspected;
            if ((string)$payment['state']==='not_configured') {
                $queue('store:payment_gateway', 'sales', 'اخذ و تأیید مستندات رسمی درگاه پرداخت فروشگاه',
                    'ارائه‌دهنده ثبت‌شده: '.(string)$payment['provider'].
                    '؛ قرارداد پذیرندگی، احراز مالکیت، اعتبارسنجی callback و مدرک تسویه لازم است. تا آن زمان هیچ پرداختی تأییدشده نیست.',
                    'critical');
            }
        }
        $enabled = (int)$store->query('SELECT COUNT(*) FROM products WHERE enabled=1')->fetchColumn();
        ++$inspected;
        if ($enabled>0 && $payment && (string)$payment['state']==='not_configured') {
            $queue('store:products_without_gateway', 'sales', 'کنترل فروش محصولات فعال بدون درگاه تأییدشده',
                'تعداد محصولات فعال: '.$enabled.'؛ قبل از ادعای فروش یا دریافت وجه، مسیر پرداخت و تحویل واقعی را تأیید کنید.',
                'high');
        }
        $hasDrafts = (int)$store->query("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='factory_drafts'")->fetchColumn();
        if ($hasDrafts) {
            $drafts = (int)$store->query('SELECT COUNT(*) FROM factory_drafts')->fetchColumn();
            ++$inspected;
            if ($drafts>0) {
                $queue('store:factory_drafts', 'sales', 'بررسی تجاری و حقوقی پیش‌نویس‌های کارخانه',
                    'تعداد پیش‌نویس‌های واردشده: '.$drafts.'؛ مجوز عرضه، محتوای قابل تحویل و قیمت باید پیش از انتشار بررسی شوند.',
                    'high');
            }
        }
    }
    $inbox = zmCcBridgeReadOnly($private.'/master_customer_inbox.sqlite3');
    if ($inbox !== null) {
        // Keep personal names, emails and message bodies out of the command-center task store.
        $messages = $inbox->query("SELECT id,kind,processing_status FROM customer_questions
            WHERE tenant='zomorod' ORDER BY created_utc DESC,id DESC LIMIT 30")->fetchAll();
        foreach ($messages as $message) {
            ++$inspected;
            $ticket = (string)$message['id'];
            if (!preg_match('/^[a-f0-9]{24}$/D', $ticket)) continue;
            $isOrderClaim = (string)$message['kind']==='order_question';
            $isPending = (string)$message['processing_status']!=='handled';
            $queue('customer:'.$ticket, 'sales', 'بررسی درخواست واقعی مشتری #'.substr($ticket,0,10),
                'پیام مشتری در صندوق خصوصی ثبت شده است. وضعیت پردازش: '.(string)$message['processing_status'].
                '؛ مشاهده: /business/customer_inbox.php. '.
                ($isOrderClaim ? 'مرجع سفارش صرفاً ادعای مشتری است و پرداخت یا فروش را اثبات نمی‌کند.' :
                    'ثبت پرسش به‌معنای سفارش یا پرداخت نیست.'),
                $isPending ? 'high' : 'normal');
        }
    }
    return ['created'=>$created, 'inspected'=>$inspected, 'sources'=>$sources];
}

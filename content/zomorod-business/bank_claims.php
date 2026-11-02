<?php
declare(strict_types=1);
/**
 * Pending bank receipt claims. This code never writes ledger, invoice_payments,
 * bank_payment_evidence, or bank provider APIs. Claims are NOT settled funds.
 * Call only within an authenticated, CSRF-checked BEGIN IMMEDIATE transaction.
 */
function zbClaimReceipt(PDO $db, int $actorId, string $invoiceInput,
                        int $bankAccountId, string $amountInput,
                        string $claimedOn, string $externalRef): int {
    if(!preg_match('/^[1-9][0-9]{0,17}$/D',$invoiceInput))zbReject('شناسه فاکتور نامعتبر است.');
    $invoiceId=filter_var($invoiceInput,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    if($invoiceId===false)zbReject('شناسه فاکتور نامعتبر است.');
    $amount=zbCents($amountInput);
    if($amount<=0)zbReject('مبلغ باید مثبت باشد.');
    $date=DateTimeImmutable::createFromFormat('!Y-m-d',$claimedOn);
    $now=new DateTimeImmutable('now',new DateTimeZone('Asia/Tehran'));
    if(!$date||$date->format('Y-m-d')!==$claimedOn||$claimedOn>$now->format('Y-m-d'))
        zbReject('تاریخ رسید نامعتبر یا در آینده است.');
    $length=function_exists('mb_strlen')?mb_strlen($externalRef,'UTF-8'):strlen($externalRef);
    if($length<6||$length>100||preg_match('/[\x00-\x1f\x7f]/',$externalRef))
        zbReject('شناسه مرجع باید ۶ تا ۱۰۰ نویسه و بدون کاراکتر کنترلی باشد.');
    $bank=$db->prepare("SELECT code FROM ledger_accounts WHERE id=? AND active=1 AND type='asset'");
    $bank->execute([$bankAccountId]);
    $bankCode=$bank->fetchColumn();
    if(!in_array($bankCode,['1011','1012'],true))zbReject('حساب بانکی مجاز نیست.',409);
    $s=$db->prepare("SELECT i.id,i.currency,i.invoice_date,i.amount,
            COALESCE((SELECT SUM(p.amount) FROM invoice_payments p WHERE p.invoice_id=i.id),0) AS paid,
            COALESCE((SELECT SUM(c.amount) FROM bank_receipt_claims c WHERE c.invoice_id=i.id AND c.status='pending'),0) AS pending
            FROM invoices i WHERE i.id=?");
    $s->execute([$invoiceId]);$invoice=$s->fetch(PDO::FETCH_ASSOC);
    if(!$invoice)zbReject('فاکتور وجود ندارد.',404);
    if($invoice['currency']!=='IRR')zbReject('این مسیر فقط فاکتور ریالی را می‌پذیرد.');
    if($claimedOn<$invoice['invoice_date'])zbReject('تاریخ ادعای پرداخت نمی‌تواند پیش از تاریخ فاکتور باشد.');
    $available=(int)$invoice['amount']-(int)$invoice['paid']-(int)$invoice['pending'];
    if($available<=0||$amount>$available)zbReject('مبلغ از مانده آزاد فاکتور بیشتر است؛ ادعاهای در انتظار نیز منظور می‌شوند.',409);
    $duplicate=$db->prepare('SELECT id FROM bank_receipt_claims WHERE bank_account_id=? AND external_ref=?');
    $duplicate->execute([$bankAccountId,$externalRef]);
    if($duplicate->fetchColumn()!==false)zbReject('این مرجع قبلاً برای همین بانک دریافت شده است.',409);
    $insert=$db->prepare("INSERT INTO bank_receipt_claims
        (invoice_id,bank_account_id,amount,claimed_on,external_ref,status,created_by)
        VALUES (?,?,?,?,?,'pending',?)");
    $insert->execute([$invoiceId,$bankAccountId,$amount,$claimedOn,$externalRef,$actorId]);
    $id=(int)$db->lastInsertId();
    $audit=$db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id) VALUES(?,?,?,?)');
    $audit->execute([$actorId,'submit','unverified-bank-claim',$id]);
    return $id;
}

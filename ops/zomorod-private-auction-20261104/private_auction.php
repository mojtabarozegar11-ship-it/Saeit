<?php
declare(strict_types=1);

/**
 * Private, internal tender register for Zomorod's authenticated management desk.
 * This does not publish tenders, message suppliers, award contracts, transfer
 * funds, or accept an external bid. Every offer is registered by an authorised
 * company user against an already-recorded evidence document.
 *
 * Required host functions: authorize, actor, role, req, esc, cents, validDate,
 * q, one, audit, uniqueNo, formBegin, tokenInput, today, bail.
 */

function zmAuctionSchema(PDO $db): void
{
    $db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS zm_private_auctions (
    id INTEGER PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 5 AND 180),
    description TEXT NOT NULL CHECK(length(description) BETWEEN 12 AND 2500),
    currency TEXT NOT NULL CHECK(currency IN ('IRR','USD','EUR','AED')),
    opens_on TEXT NOT NULL,
    closes_on TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','open','closed','cancelled')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(closes_on>=opens_on)
)
SQL);
    $db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS zm_private_auction_offers (
    id INTEGER PRIMARY KEY,
    auction_id INTEGER NOT NULL REFERENCES zm_private_auctions(id),
    party_id INTEGER NOT NULL REFERENCES parties(id),
    evidence_doc_id INTEGER NOT NULL REFERENCES documents(id),
    offer_reference TEXT NOT NULL CHECK(length(offer_reference) BETWEEN 3 AND 80),
    amount INTEGER NOT NULL CHECK(amount>0),
    registered_by INTEGER NOT NULL REFERENCES users(id),
    registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(auction_id,offer_reference)
)
SQL);
    $db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS zm_private_auction_events (
    id INTEGER PRIMARY KEY,
    auction_id INTEGER NOT NULL REFERENCES zm_private_auctions(id),
    event TEXT NOT NULL CHECK(event IN ('created','opened','closed','cancelled','offer_registered')),
    explanation TEXT NOT NULL DEFAULT '',
    offer_id INTEGER REFERENCES zm_private_auction_offers(id),
    actor_id INTEGER NOT NULL REFERENCES users(id),
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
SQL);
    $db->exec('CREATE INDEX IF NOT EXISTS zm_auction_offers_by_auction ON zm_private_auction_offers(auction_id,registered_at)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_auction_events_by_auction ON zm_private_auction_events(auction_id,recorded_at)');
    $db->exec('CREATE INDEX IF NOT EXISTS zm_auctions_by_state ON zm_private_auctions(state,closes_on)');
}

function zmAuctionManager(): bool
{
    return in_array(role(), ['admin', 'manager'], true);
}

function zmAuctionInteger(string $key): int
{
    $value = req($key);
    if (!preg_match('/^[1-9][0-9]{0,8}$/D', $value)) {
        bail('شناسهٔ واردشده معتبر نیست.');
    }
    return (int) $value;
}

function zmAuctionEvent(PDO $db, int $auctionId, string $event, string $explanation = '', ?int $offerId = null): void
{
    $stmt = $db->prepare('INSERT INTO zm_private_auction_events (auction_id,event,explanation,offer_id,actor_id) VALUES (?,?,?,?,?)');
    $stmt->execute([$auctionId,$event,$explanation,$offerId,actor()]);
    audit($db, $event, 'private-auction', $auctionId);
}

function zmAuctionHandle(PDO $db, string $action): void
{
    authorize('manage');
    if (!zmAuctionManager()) {
        bail('ثبت و تغییر مزایده فقط برای مدیر یا مدیرکل مجاز است.', 403);
    }
    zmAuctionSchema($db);
    $now = today();
    $db->beginTransaction();
    try {
        if ($action === 'zm_auction_create') {
            $title = req('title');
            $description = req('description');
            $currency = req('currency');
            $opens = req('opens_on');
            $closes = req('closes_on');
            $titleLength = function_exists('mb_strlen') ? mb_strlen($title, 'UTF-8') : strlen($title);
            $descriptionLength = function_exists('mb_strlen') ? mb_strlen($description, 'UTF-8') : strlen($description);
            if ($titleLength < 5 || $titleLength > 180 || $descriptionLength < 12 || $descriptionLength > 2500) {
                bail('عنوان یا شرح مزایده خارج از طول مجاز است.');
            }
            if (!in_array($currency, ['IRR','USD','EUR','AED'], true) || !validDate($opens) || !validDate($closes) || $closes < $opens) {
                bail('ارز یا بازهٔ تاریخ مزایده معتبر نیست.');
            }
            $stmt = $db->prepare("INSERT INTO zm_private_auctions (reference,title,description,currency,opens_on,closes_on,state,created_by) VALUES (?,?,?,?,?,?,'draft',?)");
            $stmt->execute([uniqueNo('AUC'),$title,$description,$currency,$opens,$closes,actor()]);
            $id = (int) $db->lastInsertId();
            zmAuctionEvent($db,$id,'created','پیش‌نویس داخلی؛ بدون انتشار یا تعهد مالی');
        } elseif ($action === 'zm_auction_open') {
            $id = zmAuctionInteger('auction_id');
            $stmt = $db->prepare("UPDATE zm_private_auctions SET state='open',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state='draft' AND opens_on<=? AND closes_on>=?");
            $stmt->execute([$id,$now,$now]);
            if ($stmt->rowCount() !== 1) {
                bail('فقط پیش‌نویس در بازهٔ تاریخ معتبر قابل گشایش داخلی است.');
            }
            zmAuctionEvent($db,$id,'opened','گشایش داخلی؛ بدون اطلاع‌رسانی به بیرون');
        } elseif ($action === 'zm_auction_close') {
            $id = zmAuctionInteger('auction_id');
            $reason = req('reason');
            if (strlen($reason) < 12 || strlen($reason) > 700) {
                bail('دلیل بستن مزایده باید بین ۱۲ تا ۷۰۰ نویسه باشد.');
            }
            $stmt = $db->prepare("UPDATE zm_private_auctions SET state='closed',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state='open'");
            $stmt->execute([$id]);
            if ($stmt->rowCount() !== 1) {
                bail('فقط مزایدهٔ باز قابل بستن است.');
            }
            zmAuctionEvent($db,$id,'closed',$reason);
        } elseif ($action === 'zm_auction_cancel') {
            $id = zmAuctionInteger('auction_id');
            $reason = req('reason');
            if (strlen($reason) < 12 || strlen($reason) > 700) {
                bail('دلیل لغو مزایده باید بین ۱۲ تا ۷۰۰ نویسه باشد.');
            }
            $stmt = $db->prepare("UPDATE zm_private_auctions SET state='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state IN ('draft','open')");
            $stmt->execute([$id]);
            if ($stmt->rowCount() !== 1) {
                bail('این مزایده قابل لغو نیست.');
            }
            zmAuctionEvent($db,$id,'cancelled',$reason);
        } elseif ($action === 'zm_auction_offer') {
            $id = zmAuctionInteger('auction_id');
            $party = zmAuctionInteger('party_id');
            $evidence = zmAuctionInteger('evidence_doc_id');
            $reference = req('offer_reference');
            $amount = cents(req('amount'));
            if (strlen($reference) < 3 || strlen($reference) > 80 || $amount <= 0) {
                bail('شمارهٔ پیشنهاد یا مبلغ معتبر نیست.');
            }
            if ((int) one($db,"SELECT COUNT(*) FROM parties WHERE id=? AND kind IN ('supplier','both')",[$party]) !== 1) {
                bail('پیشنهاددهنده باید در فهرست تأمین‌کنندگان ثبت شده باشد.');
            }
            if ((int) one($db,'SELECT COUNT(*) FROM documents WHERE id=?',[$evidence]) !== 1) {
                bail('سند پشتیبانِ ثبت‌شده لازم است.');
            }
            $stmt = $db->prepare(<<<'SQL'
INSERT INTO zm_private_auction_offers(auction_id,party_id,evidence_doc_id,offer_reference,amount,registered_by)
SELECT id,?,?,?,?,? FROM zm_private_auctions
WHERE id=? AND state='open' AND opens_on<=? AND closes_on>=?
SQL);
            $stmt->execute([$party,$evidence,$reference,$amount,actor(),$id,$now,$now]);
            if ($stmt->rowCount() !== 1) {
                bail('مزایده باز نیست یا تاریخ دریافت پیشنهاد پایان یافته است.');
            }
            $offerId = (int) $db->lastInsertId();
            zmAuctionEvent($db,$id,'offer_registered','ثبت مستند پیشنهاد توسط کاربر داخلی',$offerId);
        } else {
            bail('عملیات مزایده شناخته نشد.', 404);
        }
        $db->commit();
    } catch (Throwable $error) {
        if ($db->inTransaction()) {
            $db->rollBack();
        }
        throw $error;
    }
}

function zmAuctionStateLabel(string $state): string
{
    return [
        'draft' => 'پیش‌نویس',
        'open' => 'باز (فقط داخلی)',
        'closed' => 'بسته',
        'cancelled' => 'لغوشده',
    ][$state] ?? 'نامشخص';
}

function zmAuctionRender(PDO $db): void
{
    authorize('view');
    zmAuctionSchema($db);
    $auctions = q($db,'SELECT a.*,u.username AS creator_name, (SELECT COUNT(*) FROM zm_private_auction_offers o WHERE o.auction_id=a.id) AS offer_count FROM zm_private_auctions a JOIN users u ON u.id=a.created_by ORDER BY a.id DESC LIMIT 150');
    $manager = zmAuctionManager();
    echo '<section><h2>دفتر مزایده‌های خصوصی</h2><p class="muted">این بخش فقط در محیط مدیریت شرکت در دسترس است. ثبت مزایده یا پیشنهاد به‌معنی انتشار عمومی، دعوت تأمین‌کننده، پذیرش قیمت، انعقاد قرارداد یا ایجاد تعهد مالی نیست. تمام تغییرات دارای ردپای حسابرسی است.</p>';
    echo '<div class="scroll"><table><thead><tr><th>شماره</th><th>عنوان</th><th>مهلت</th><th>وضعیت</th><th>پیشنهاد مستند</th></tr></thead><tbody>';
    foreach ($auctions as $auction) {
        echo '<tr><td>'.esc($auction['reference']).'</td><td>'.esc($auction['title']).'</td><td>'.esc($auction['closes_on']).'</td><td>'.esc(zmAuctionStateLabel((string)$auction['state'])).'</td><td>'.esc($auction['offer_count']).'</td></tr>';
    }
    if (!$auctions) {
        echo '<tr><td colspan="5">هنوز مزایده‌ای ثبت نشده است.</td></tr>';
    }
    echo '</tbody></table></div></section>';
    if (!$manager) {
        return;
    }
    echo '<section><h3>ثبت مزایدهٔ خصوصی (پیش‌نویس)</h3>';
    formBegin('zm_auction_create');
    echo '<div class="form"><div><label>عنوان</label><input name="title" minlength="5" maxlength="180" required></div><div><label>ارز</label><select name="currency"><option value="IRR">IRR</option><option value="USD">USD</option><option value="EUR">EUR</option><option value="AED">AED</option></select></div>';
    echo '<div><label>آغاز دریافت پیشنهاد</label><input name="opens_on" type="date" value="'.esc(today()).'" required></div><div><label>پایان دریافت پیشنهاد</label><input name="closes_on" type="date" value="'.esc(today()).'" required></div>';
    echo '<div class="full"><label>شرح دقیق، شرایط و معیارهای ارزیابی</label><textarea name="description" minlength="12" maxlength="2500" required></textarea></div></div><button>ذخیرهٔ پیش‌نویس</button></form></section>';

    $drafts = array_filter($auctions,static fn(array $a):bool => $a['state']==='draft' && $a['opens_on']<=today() && $a['closes_on']>=today());
    $open = array_filter($auctions,static fn(array $a):bool => $a['state']==='open');
    if ($drafts) {
        echo '<section><h3>گشایش داخلی پیش‌نویس</h3>';
        formBegin('zm_auction_open');
        echo '<label>انتخاب پیش‌نویس</label><select name="auction_id" required>';
        foreach ($drafts as $auction) {
            echo '<option value="'.esc($auction['id']).'">'.esc($auction['reference'].' · '.$auction['title']).'</option>';
        }
        echo '</select><button>گشایش داخلی</button></form></section>';
    }
    if ($open) {
        $parties = q($db,"SELECT id,name FROM parties WHERE kind IN ('supplier','both') ORDER BY name,id LIMIT 300");
        $docs = q($db,'SELECT id,title FROM documents ORDER BY id DESC LIMIT 300');
        echo '<section><h3>ثبت پیشنهاد دارای مستندات</h3>';
        if (!$parties || !$docs) {
            echo '<p class="notice">برای ثبت پیشنهاد واقعی، ابتدا تأمین‌کننده را در «اشخاص» و سند پشتیبان او را در «مکاتبات» وارد کنید. پیشنهاد بدون سند ثبت نخواهد شد.</p>';
        } else {
            formBegin('zm_auction_offer');
            echo '<div class="form"><div><label>مزایده باز</label><select name="auction_id" required>';
            foreach ($open as $auction) {
                echo '<option value="'.esc($auction['id']).'">'.esc($auction['reference'].' · '.$auction['title'].' · '.$auction['currency']).'</option>';
            }
            echo '</select></div><div><label>تأمین‌کننده</label><select name="party_id" required>';
            foreach ($parties as $party) {
                echo '<option value="'.esc($party['id']).'">'.esc($party['name']).'</option>';
            }
            echo '</select></div><div><label>سند پشتیبان</label><select name="evidence_doc_id" required>';
            foreach ($docs as $document) {
                echo '<option value="'.esc($document['id']).'">'.esc($document['title']).'</option>';
            }
            echo '</select></div><div><label>شماره یکتای پیشنهاد</label><input name="offer_reference" minlength="3" maxlength="80" required></div>';
            echo '<div><label>مبلغ پیشنهاد در واحد ارز مزایده</label><input name="amount" inputmode="decimal" pattern="[0-9]+(\\.[0-9]{1,2})?" required></div></div><button>ثبت سند پیشنهاد بدون پذیرش آن</button></form>';
        }
        echo '</section>';
        echo '<section><h3>بستن مزایده باز</h3>';
        formBegin('zm_auction_close');
        echo '<label>مزایده</label><select name="auction_id" required>';
        foreach ($open as $auction) {
            echo '<option value="'.esc($auction['id']).'">'.esc($auction['reference'].' · '.$auction['title']).'</option>';
        }
        echo '</select><label>دلیل بستن</label><textarea name="reason" minlength="12" maxlength="700" required></textarea><button>بستن و حفظ سوابق</button></form></section>';
    }
    $cancellable = array_filter($auctions,static fn(array $a):bool => in_array($a['state'],['draft','open'],true));
    if ($cancellable) {
        echo '<section><h3>لغو با ثبت دلیل</h3>';
        formBegin('zm_auction_cancel');
        echo '<label>مزایده</label><select name="auction_id" required>';
        foreach ($cancellable as $auction) {
            echo '<option value="'.esc($auction['id']).'">'.esc($auction['reference'].' · '.$auction['title']).'</option>';
        }
        echo '</select><label>دلیل لغو</label><textarea name="reason" minlength="12" maxlength="700" required></textarea><button>لغو بدون حذف سوابق</button></form></section>';
    }
    $offers = q($db,'SELECT o.id,o.offer_reference,o.amount,o.registered_at,a.reference AS auction_reference,a.currency,p.name AS party_name,d.title AS evidence_title,u.username AS registrar FROM zm_private_auction_offers o JOIN zm_private_auctions a ON a.id=o.auction_id JOIN parties p ON p.id=o.party_id JOIN documents d ON d.id=o.evidence_doc_id JOIN users u ON u.id=o.registered_by ORDER BY o.id DESC LIMIT 150');
    echo '<section><h3>دفتر پیشنهادهای مستند (غیرقابل‌ویرایش)</h3><div class="scroll"><table><thead><tr><th>مزایده</th><th>شماره پیشنهاد</th><th>تأمین‌کننده</th><th>مبلغ</th><th>سند</th><th>ثبت‌کننده</th></tr></thead><tbody>';
    foreach ($offers as $offer) {
        echo '<tr><td>'.esc($offer['auction_reference']).'</td><td>'.esc($offer['offer_reference']).'</td><td>'.esc($offer['party_name']).'</td><td>'.esc(number_format((int)$offer['amount']/100,2,'.',',').' '.$offer['currency']).'</td><td>'.esc($offer['evidence_title']).'</td><td>'.esc($offer['registrar']).'</td></tr>';
    }
    if (!$offers) {
        echo '<tr><td colspan="6">هنوز پیشنهاد مستندی ثبت نشده است.</td></tr>';
    }
    echo '</tbody></table></div></section>';
}

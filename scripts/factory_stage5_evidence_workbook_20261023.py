#!/usr/bin/env python3
"""Private evidence-linked stage 5 educational workbook drafts -> stage 6 review queue.

Produces real bilingual Markdown files from research-linked curricula and
transparent original exercises. These are educational *drafts*, not verified
agronomic recommendations, a fabricated expert review, QA1000, or stock goods.
No network, website write, human impersonation, payment or publication.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA = "saeit.factory.stage5-evidence-workbook.v1"
REVIEW = "saeit.factory.stage6-independent-review-request.v1"
MAX_TEXT_BYTES = 400000
MIN_UNITS = 5
WORKBOOK_LOCALES = ("fa-IR", "en-US")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_stage34(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("STAGE5_DEPENDENCY_NOT_REGULAR")
    spec = importlib.util.spec_from_file_location("stage34_dependency", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized(value, limit=650):
    if not isinstance(value, str):
        raise ValueError("STAGE5_TEXT_EXPECTED")
    value = " ".join(value.replace("\x00", " ").split())
    if not value or len(value) > limit:
        raise ValueError("STAGE5_TEXT_LENGTH")
    return value.replace("<", "&lt;").replace(">", "&gt;")


def write_once(path, body, lib):
    lib.private_dir(path.parent)
    if path.is_symlink():
        raise RuntimeError("STAGE5_SYMLINK_TARGET")
    if path.exists():
        if not path.is_file() or path.read_bytes() != body:
            raise RuntimeError("STAGE5_IMMUTABLE_DRAFT_MISMATCH:" + path.name)
        return False
    fd, temporary = tempfile.mkstemp(prefix=".stage5-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        if path.exists() or path.is_symlink():
            raise RuntimeError("STAGE5_CONCURRENT_TARGET")
        os.replace(temporary, path)
        return True
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verified_stage4(area, name, lib):
    if lib.NAME.fullmatch(name) is None:
        raise RuntimeError("STAGE5_INVALID_NAME")
    handoff = lib.read(area / "stage-05" / "inbox" / name)
    prototype = lib.read(area / "stage-04" / "completed-prototypes" / name)
    design = lib.read(area / "stage-03" / "completed-designs" / name)
    receipt = lib.read(area / "stage-04" / "receipts" / name)
    _, research, order, editions = lib.verified_stage2(area, name)
    if (handoff.get("schema") != lib.HANDOFF
            or handoff.get("previous_stage") != 4 or handoff.get("next_stage") != 5
            or handoff.get("order_id") != prototype.get("order_id")
            or handoff.get("revision") != prototype.get("revision")
            or handoff.get("stage4_prototype_sha256") != lib.digest(prototype)
            or handoff.get("stage3_design_sha256") != lib.digest(design)
            or prototype.get("schema") != lib.PROTOTYPE
            or prototype.get("stage3_design_sha256") != lib.digest(design)
            or design.get("schema") != lib.DESIGN
            or design.get("stage2_research_sha256") != lib.digest(research)
            or receipt.get("schema") != lib.HANDOFF
            or receipt.get("stage_4_prototype_completed") is not True
            or receipt.get("prototype_sha256") != lib.digest(prototype)
            or receipt.get("stage_5_packet_sha256") != lib.digest(handoff)
            or len(design.get("chapters", [])) < MIN_UNITS
            or len(prototype.get("bilingual_sample_activities", [])) < MIN_UNITS):
        raise RuntimeError("STAGE5_STAGE4_CHAIN_INTEGRITY_FAILED")
    for obj in (handoff, prototype, design, research):
        lib.deny_approval(obj)
    return handoff, prototype, design, research, order, editions


def book_unit(unit, claim, loc):
    n = unit["unit"]
    statement = normalized(claim["statement"], 1500)
    citations = ", ".join(normalized(x, 100) for x in claim["source_ids"])
    synthetic = 12 + n
    observed = 2 + n % 4
    pct = round(observed * 100 / synthetic, 2)
    if loc == "fa-IR":
        return f"""## فصل {n}: {normalized(unit['title_fa'])}

### هدف و پرسش پژوهشی
این بخش به شما کمک می‌کند تفاوت میان یک ادعای پژوهشی، شرایط اعتبار آن و یک توصیه اجرایی را بشناسید. هدف، تمرین روش بررسی شواهد مرتبط با موضوع این فصل است؛ نه صدور دستور کشت یا درمان. پیش از استفاده از هر نتیجه در مزرعه، باید اقلیم، خاک، رقم، زمان، تجهیزات، ایمنی و اعتبار خود مقاله بررسی شود.

### گزاره استخراج‌شده برای بررسی متخصص
«{statement}»

شناسه ارجاعات این گزاره: {citations}. این متن برگرفته از یادداشت پژوهشی مرحله دوم است؛ صحت نهایی، متن کامل مقاله، اندازه اثر و دامنه کاربرد آن هنوز به تأیید متخصص مستقل نیاز دارد. در گزارش خود گزاره را از تفسیرتان جدا کنید. اگر چکیده فقط همبستگی نشان می‌دهد، از آن نتیجه علی نگیرید.

### فعالیت عملیِ قابل تکرار
۱. برای هر منبع، عنوان، نویسنده، سال، شناسه پایدار و نوع مطالعه را از نسخه اصلی پیدا کنید.
۲. واحد اندازه‌گیری، جمعیت مورد مطالعه، محل و دوره آزمایش را در جدول ثبت کنید.
۳. متغیر نتیجه، متغیرهای مداخله‌گر و مقایسهٔ پایه را مشخص کنید.
۴. سه محدودیت انتقال نتیجه به شرایط ایران را بنویسید و تعیین کنید چه داده‌ای برای رفع آن‌ها لازم است.
۵. یک آزمون کوچک غیرمخرب طراحی کنید و پیش از شروع، معیار توقف و روش ثبت خطا را مشخص کنید.

### مثال محاسباتیِ ساختگی و شفاف
فرض کنید در یک تمرین کاغذی، از {synthetic} مشاهده ساختگی، {observed} مورد دارای نشانه تعریف‌شده باشند. نسبت مشاهده‌شده برابر {observed}/{synthetic} یا {pct} درصد است. این اعداد صرفاً برای آموزش روش محاسبه ساخته شده‌اند، داده مزرعه یا نتیجه مقاله نیستند. بدون گروه مقایسه، عدم قطعیت و کنترل خطا نباید درباره اثربخشی روش‌ها داوری کرد.

### تمرین و کلید پاسخ
- پرسش ۱: چرا ارتباط آماری، به‌تنهایی دلیل علیت نیست؟
- پاسخ ۱: چون عوامل پنهان، سوگیری انتخاب و تغییرات محیطی می‌توانند هر دو متغیر را تحت تأثیر قرار دهند.
- پرسش ۲: چه زمانی می‌توان نتیجه منبع را به یک موقعیت محلی منتقل کرد؟
- پاسخ ۲: پس از سنجش شباهت جمعیت، شرایط محیط، روش اندازه‌گیری، دامنه نمونه و بررسی مستقل خطرها.
- پرسش ۳: محاسبه نسبت مثال را بازسازی کنید.
- پاسخ ۳: شمار مشاهدات مشخص‌شده تقسیم بر کل مشاهدات، ضرب در صد؛ یعنی {pct} درصد در داده‌های ساختگی بالا.

### برگ ثبت کار
شناسه منبع | تاریخ بررسی | پارامتر و واحد | شرایط محیطی | محدودیت | یافته قابل تأیید | اختلاف نظر | وضعیت بازبینی.

### مرز ایمنی و کیفیت
این فصل توصیه مصرف نهاده، دارو، سم یا مداخله روی انسان و دام ارائه نمی‌دهد. هر ادعای اجرایی باید پس از مراجعه به متن کامل منبع، الزامات محلی و تأیید مستقل متخصص درج شود.
"""
    return f"""## Chapter {n}: {normalized(unit['title_en'])}

### Learning objective and research question
This unit teaches how to separate a reported research claim, its validity conditions, and a practical recommendation. It is a method for examining evidence related to this unit's topic, not a crop treatment or application instruction. Check climate, soil, variety, season, equipment, safety and the full underlying paper before using results in a real setting.

### Indexed research statement awaiting expert verification
“{statement}”

Linked source identifiers: {citations}. This statement comes from a Stage-2 desk-research workpaper. Its accuracy, the full study, effect size, and applicable population have not yet been independently certified. Keep the cited statement separate from your own interpretation. Correlation in an abstract is not sufficient grounds for a causal recommendation.

### Reproducible field-learning activity
1. Locate each original publication and record author, year, persistent identifier and study design.
2. Record measurement units, population, study location and observation period in a traceability table.
3. Distinguish outcome variables, confounders and the baseline comparison.
4. Identify three reasons why a finding might not transfer to a different local farm.
5. Design a small non-destructive observation protocol with stopping and error-recording rules.

### Explicitly synthetic worked arithmetic
For a paper exercise only, suppose {observed} of {synthetic} invented observations meet a predefined condition. The illustrative rate is {observed}/{synthetic}, or {pct} percent. These invented figures are not field data or results from the cited study. Without a comparison group, uncertainty analysis and error controls, they do not establish an intervention's effectiveness.

### Assessment with an answer key
- Question 1: Why does a statistical association alone not prove causality?
- Answer 1: Confounding, selection bias and environmental variation can influence both variables.
- Question 2: What is needed before applying an external research result locally?
- Answer 2: Compare populations, environmental conditions, measurement methods, sample boundaries and independently reviewed risks.
- Question 3: Reproduce the arithmetic in the worked example.
- Answer 3: Divide the number meeting the condition by all observations and multiply by 100; here the synthetic rate is {pct} percent.

### Reusable evidence record
Source ID | Date checked | Variable and unit | Field conditions | Limitation | Verifiable finding | Disagreement | Review status.

### Safety and quality boundary
This unit does not prescribe pesticide, veterinary drug, fertilizer or human treatment use. Any operational recommendation requires the complete source, the applicable local rules and independent expert review.
"""


def build_text(design, research, editions, loc):
    scope = normalized(research["locale_scopes"][loc], 2000)
    title = normalized(editions[loc]["title"], 300)
    audience = normalized(editions[loc]["audience"], 300)
    by_id = {c["id"]: c for c in research["claims"]}
    lines = [f"# {title}", "", f"Edition: {loc}. Intended audience: {audience}.",
             "", "PRIVATE EDUCATIONAL WORKING DRAFT — independent scientific review pending.",
             "", "Scope and transfer limitations: " + scope, ""]
    units = design["chapters"]
    for unit in units:
        claim = by_id.get(unit["source_claim_id"])
        if claim is None or set(unit["source_ids"]) != set(claim["source_ids"]):
            raise RuntimeError("STAGE5_UNIT_CLAIM_LINK_INVALID")
        lines.append(book_unit(unit, claim, loc))
    lines.extend(["", "## Bibliography / کتابنامه", ""])
    for entry in research["sources"]:
        lines.append("- " + normalized(entry["id"], 100) + " — " +
                     normalized(entry["publisher"], 220) + ": " +
                     normalized(entry["title"], 400) + " (" +
                     normalized(entry["url"], 500) + ")")
    lines.extend(["", "## Review and version policy", "",
                  "Before final release: check every original full source; verify all "
                  "agronomic assertions, safety limits and local applicability; "
                  "obtain attributable independent reviews; perform practical testing; "
                  "record defects and corrections. No automatic QA1000 or sale."])
    text = "\n".join(lines) + "\n"
    if len(units) < MIN_UNITS or len(text.split()) < 1000:
        raise RuntimeError("STAGE5_DRAFT_TOO_SHORT")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise RuntimeError("STAGE5_DRAFT_TOO_LARGE")
    return text


def stage5(area, name, lib):
    handoff, prototype, design, research, order, editions = verified_stage4(area, name, lib)
    drafts = {loc: build_text(design, research, editions, loc) for loc in WORKBOOK_LOCALES}
    source_hashes = {loc: sha_bytes(drafts[loc].encode("utf-8")) for loc in WORKBOOK_LOCALES}
    manifest = {
        "schema": SCHEMA, "stage": 5, "order_id": handoff["order_id"],
        "revision": handoff["revision"],
        "stage4_prototype_sha256": lib.digest(prototype),
        "stage3_design_sha256": lib.digest(design),
        "stage2_research_sha256": lib.digest(research),
        "manuscript_files": {loc: f"{name[:-5]}/{loc}.md" for loc in WORKBOOK_LOCALES},
        "manuscript_sha256": source_hashes,
        "chapter_count": len(design["chapters"]),
        "draft_kind": "original_bilingual_evidence_method_workbook",
        "draft_files_created": True,
        "independent_scientific_review": False,
        "domain_accuracy_certified": False,
        "real_world_field_testing": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }
    review = {
        "schema": REVIEW, "stage": 6, "order_id": handoff["order_id"],
        "revision": handoff["revision"],
        "stage5_manifest_sha256": lib.digest(manifest),
        "stage4_prototype_sha256": lib.digest(prototype),
        "status": "pending_independent_qualified_reviewer",
        "review_required": ["verify_original_full_source_text_and_metadata",
            "check_each_claim_and_scientific_scope", "review_persian_and_english_editions",
            "test_educational_usefulness_and_safety", "check_topic_specific_regulation",
            "record_attributable_reviewer_and_corrections"],
        "human_review_completed": False, "reviewer_signature_created": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }
    receipt = {
        "schema": SCHEMA, "stage_5_working_draft_created": True,
        "order_id": handoff["order_id"], "revision": handoff["revision"],
        "stage5_manifest_sha256": lib.digest(manifest),
        "stage6_review_packet_sha256": lib.digest(review),
        "stage_6_inbox_file": name,
        "human_review_completed": False, "quality1000_approved": False
    }
    folder = area / "stage-05" / "drafts" / name[:-5]
    for loc, body in drafts.items():
        write_once(folder / (loc + ".md"), body.encode("utf-8"), lib)
    created = lib.once(area / "stage-05" / "completed-drafts" / name, manifest)
    lib.once(area / "stage-06" / "inbox" / name, review)
    lib.once(area / "stage-05" / "receipts" / name, receipt)
    return created


def fair_batch(area, names, batch, lib):
    """Durable rotating selection so a failed/finished prefix cannot starve later work."""
    cursor_path = area / "stage-05" / "round-robin-cursor.json"
    if cursor_path.is_symlink():
        raise RuntimeError("STAGE5_CURSOR_SYMLINK")
    state = lib.read(cursor_path) if cursor_path.exists() else {
        "schema": "saeit.factory.stage5.round-robin.v1", "next_index": 0}
    if (state.get("schema") != "saeit.factory.stage5.round-robin.v1"
            or type(state.get("next_index")) is not int
            or state["next_index"] < 0):
        raise RuntimeError("STAGE5_CURSOR_INVALID")
    total = len(names)
    start = state["next_index"] % total if total else 0
    count = min(batch, total)
    chosen = [names[(start + i) % total] for i in range(count)]
    next_state = {"schema": "saeit.factory.stage5.round-robin.v1",
                  "next_index": (start + count) % total if total else 0}
    return chosen, cursor_path, next_state


def execute(root, lib, batch=200, only_order_id=None, excluded_orders=None):
    if only_order_id is not None and (not isinstance(only_order_id, str)
                                   or re.fullmatch(r"WO-[0-9]{8}", only_order_id) is None):
        raise RuntimeError("STAGE5_TARGET_ORDER_INVALID")
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError("STAGE5_PRIVATE_ROOT_MISSING")
    area = root / "production-instructions"
    for n in (5, 6):
        lib.private_dir(area / ("stage-%02d" % n) / "inbox")
    lock = area / ".stage5-worker.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE5_UNSAFE_LOCK")
    with lock.open("a+b") as guard:
        os.fchmod(guard.fileno(), 0o600)
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        names = sorted(p.name for p in (area / "stage-05" / "inbox").iterdir()
                       if p.is_file() and not p.is_symlink() and lib.NAME.fullmatch(p.name)
                       and (excluded_orders is None or
                            p.name.split("--r", 1)[0] not in excluded_orders))
        selected, cursor_path, next_state = fair_batch(area, names, batch, lib)
        if only_order_id is not None:
            selected = [name for name in names if name.startswith(only_order_id + "--r")][:batch]
            next_state = lib.read(cursor_path) if cursor_path.exists() else {
                "schema": "saeit.factory.stage5.round-robin.v1", "next_index": 0}
        created, blocked = 0, 0
        for name in selected:
            try:
                created += int(stage5(area, name, lib))
            except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
                blocked += 1
                lib.atomic(area / "stage-05" / "blocked" / name, {
                    "order_file": name, "stage": 5,
                    "reason": type(exc).__name__ + ":" + str(exc)[:200],
                    "status": "requires_stage5_rework_or_scientific_input",
                    "advanced_to_stage6": False})
        lib.atomic(cursor_path, next_state)
        result = {
            "stage5_inbox": len(names), "stage5_created_this_tick": created,
            "stage5_blocked_this_tick": blocked,
            "stage5_drafts_total": len(list((area / "stage-05" / "completed-drafts").glob("WO-*.json"))),
            "stage6_review_queue": len(list((area / "stage-06" / "inbox").glob("WO-*.json"))),
            "stage6_independent_reviews_completed_by_worker": 0,
            "quality1000_certifications_created": 0, "public_releases_created": 0,
            "websites_modified": False
        }
        lib.atomic(area / "stage-05" / "autonomous-status.json", result)
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--stage34-worker", default=str(Path(__file__).with_name("stage34-autonomous-handoff.py")))
    p.add_argument("--batch", type=int, default=200)
    p.add_argument("--only-order-id")
    p.add_argument("--exclude-owner-agri200", action="store_true")
    args = p.parse_args()
    if not 1 <= args.batch <= 500:
        raise RuntimeError("STAGE5_INVALID_BATCH")
    if args.only_order_id and args.exclude_owner_agri200:
        raise RuntimeError("STAGE5_CONFLICTING_SCOPE")
    if args.exclude_owner_agri200:
        from factory_strict_serial_scope_v1 import owner_agri200_ids
        excluded = owner_agri200_ids(args.factory_private)
    else:
        excluded = None
    result = execute(args.factory_private, load_stage34(args.stage34_worker), args.batch,
                     only_order_id=args.only_order_id, excluded_orders=excluded)
    for key, value in sorted(result.items()):
        print("FACTORY_STAGE5_" + key.upper() + "=" +
              (str(value).lower() if isinstance(value, bool) else str(value)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE5_ERROR=" + type(exc).__name__ + ":" + str(exc)[:200], file=sys.stderr)
        raise SystemExit(1)

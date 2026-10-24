#!/usr/bin/env python3
"""Issue 700 owner-priority, private curriculum-specific book work orders on VPS.

This creates *manufacturing instructions*, never books or commercial products.
Every title needs actual official curriculum verification and original authoring.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.factory.production-instructions.v1"
ORIGIN = "owner_requested_education700_p0"
INDEX_SCHEMA = "saeit.factory.owner-education700-p0-index.v1"
ORDER_RE = re.compile(r"WO-[0-9]{8}\.json\Z")
ID_RE = re.compile(r"EDU-(IR|EU|NA|GC)-[0-9]{3}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MIN_ORIGINAL_WORDS = 100_000
COUNTS = {"IR": 200, "EU": 200, "NA": 100, "GC": 200}
EU_COUNTRIES = (
    ("DE", "Germany", "de-DE"), ("FR", "France", "fr-FR"),
    ("GB", "United Kingdom", "en-GB"), ("IT", "Italy", "it-IT"),
    ("ES", "Spain", "es-ES"), ("NL", "Netherlands", "nl-NL"),
    ("SE", "Sweden", "sv-SE"), ("PL", "Poland", "pl-PL"),
    ("FI", "Finland", "fi-FI"), ("PT", "Portugal", "pt-PT"),
)
GULF_COUNTRIES = (
    ("SA", "عربستان سعودی", "ar-SA"), ("AE", "امارات متحده عربی", "ar-AE"),
    ("QA", "قطر", "ar-QA"), ("KW", "کویت", "ar-KW"),
    ("OM", "عمان", "ar-OM"),
)


def encoded(item: dict) -> bytes:
    return json.dumps(item, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha(item: dict) -> str:
    return hashlib.sha256(encoded(item)).hexdigest()


def source_specs() -> list[dict]:
    result: list[dict] = []

    def add(group, title, country, locale, level, discipline, mode,
            jurisdiction, *, title_is_native=True):
        ident = "EDU-%s-%03d" % (group, 1 + sum(x["group"] == group for x in result))
        result.append({
            "id": ident, "group": group, "title": title, "country": country,
            "locale": locale, "level": level, "discipline": discipline,
            "format": mode, "jurisdiction": jurisdiction,
            "native_title_verified": title_is_native,
        })

    # Iran: each of 12 school grades has four selected subjects in four
    # genuinely different instructional formats (192) plus 8 exam guides.
    modes = ("درسنامهٔ مفهومی", "کارگاه حل تمرین با پاسخ تشریحی",
             "آزمون‌های طبقه‌بندی‌شده", "رفع اشکال و یادگیری عمیق")
    for grade in range(1, 13):
        if grade <= 3:
            subjects = ("ریاضی", "فارسی", "علوم تجربی", "نگارش و سواد خواندن")
        elif grade <= 6:
            subjects = ("ریاضی", "فارسی", "علوم تجربی", "مطالعات اجتماعی")
        elif grade <= 9:
            subjects = ("ریاضی", "فارسی", "علوم تجربی", "زبان انگلیسی")
        else:
            subjects = ("ریاضی", "فارسی", "زبان انگلیسی", "دروس تخصصی رشته")
        for subject in subjects:
            for mode in modes:
                title = "%s %s پایهٔ %s ایران" % (mode, subject, grade)
                add("IR", title, "Iran", "fa-IR", "grade-%02d" % grade,
                    subject, mode, "Iran national curriculum; school stream must be verified")
    supplements = (
        "آمادگی امتحان نهایی ریاضی دوازدهم",
        "آمادگی امتحان نهایی فارسی دوازدهم",
        "آمادگی امتحان نهایی زبان انگلیسی دوازدهم",
        "آمادگی امتحان نهایی دروس تخصصی تجربی",
        "آمادگی امتحان نهایی دروس تخصصی ریاضی",
        "آمادگی امتحان نهایی دروس تخصصی انسانی",
        "مهارت‌های مطالعه برای ورود به متوسطهٔ اول",
        "راهبردهای تست‌زنی و مدیریت زمان کنکور",
    )
    for title in supplements:
        add("IR", title, "Iran", "fa-IR", "supplemental-exam",
            "exam-preparation", "guided-learning-and-practice",
            "Iran; current school examination syllabus requires official confirmation")

    # Europe is not one curriculum. Allocate 20 distinct combinations for
    # each country; final local-language titling waits for native review.
    eu_levels = ("upper-primary", "lower-secondary", "upper-secondary",
                 "examination-foundation", "vocational-foundation")
    eu_subjects = ("Mathematics", "Science", "Literacy and Writing",
                   "Digital and Computational Skills")
    for country_code, country, locale in EU_COUNTRIES:
        for level in eu_levels:
            for subject in eu_subjects:
                add("EU", "%s — %s — %s: Guided Workbook" %
                    (country, level.replace("-", " ").title(), subject),
                    country, locale, level, subject,
                    "curriculum-aligned-instruction-and-activities",
                    country_code + ": official regional/track curriculum must be verified",
                    title_is_native=(locale == "en-GB"))

    # North America: 50 US state-sensitive, 25 Ontario English,
    # 25 Québec French. Province/state applicability is not presumed.
    na_subjects = ("Mathematics", "Language and Writing", "Science",
                   "Civics and Social Studies", "Digital Literacy")
    for grade in range(6, 11):
        for subject in na_subjects:
            for mode in ("Concepts and Worked Examples", "Practice and Diagnostics"):
                add("NA", "United States Grade %s %s — %s" %
                    (grade, subject, mode), "United States", "en-US",
                    "grade-%02d" % grade, subject, mode,
                    "US state and district selection REQUIRED")
            add("NA", "Ontario Grade %s %s — Study Companion" %
                (grade, subject), "Canada", "en-CA", "grade-%02d" % grade,
                subject, "study-companion-and-diagnostics",
                "Ontario; provincial grade/course equivalence requires confirmation")
            add("NA", "Québec Secondary Equivalency %s %s — Cahier d'apprentissage" %
                (grade, subject), "Canada", "fr-CA", "candidate-grade-%02d" % grade,
                subject, "cahier-et-corrigés",
                "Québec; secondary year, language and official program must be verified",
                title_is_native=False)

    gulf_levels = ("الصفوف ١–٣", "الصفوف ٤–٦", "الصفوف ٧–٩",
                   "الصفوف ١٠–١١", "الصف الثاني عشر")
    gulf_subjects = ("اللغة العربية", "الرياضيات", "العلوم", "اللغة الإنجليزية",
                     "الدراسات الاجتماعية", "التقنية الرقمية",
                     "التربية الإسلامية", "المشاريع العلمية التطبيقية")
    for country_code, country, locale in GULF_COUNTRIES:
        for level in gulf_levels:
            for subject in gulf_subjects:
                add("GC", "الكتاب المساعد في %s — %s — %s" %
                    (subject, level, country), country, locale, level, subject,
                    "شرح وتمارين وتقويم وحلول",
                    country_code + ": ministry syllabus, grade and licensed curriculum verification required")

    validate_specs(result)
    return result


def validate_specs(rows: list[dict]) -> None:
    if len(rows) != 700:
        raise ValueError("EDUCATION_TOTAL_NOT_700")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != 700 or not all(ID_RE.fullmatch(i) for i in ids):
        raise ValueError("EDUCATION_DUPLICATE_OR_INVALID_ID")
    if len({(r["country"], r["level"], r["discipline"], r["format"],
             r["title"]) for r in rows}) != 700:
        raise ValueError("EDUCATION_DUPLICATE_PRODUCT_SCOPE")
    for group, quantity in COUNTS.items():
        subset = [r for r in rows if r["group"] == group]
        if len(subset) != quantity or [r["id"] for r in subset] != [
            "EDU-%s-%03d" % (group, n) for n in range(1, quantity + 1)]:
            raise ValueError("EDUCATION_BAD_REGIONAL_ALLOCATION:" + group)
    if len({r["country"] for r in rows if r["group"] == "EU"}) != 10:
        raise ValueError("EDUCATION_EU_COUNTRIES_INSUFFICIENT")
    if len({r["country"] for r in rows if r["group"] == "GC"}) != 5:
        raise ValueError("EDUCATION_GULF_COUNTRIES_INSUFFICIENT")
    if sum(r["country"] == "Canada" for r in rows) != 50:
        raise ValueError("EDUCATION_CANADA_ALLOCATION_WRONG")


def make_order(spec: dict, rank: int) -> dict:
    ident, locale = spec["id"], spec["locale"]
    site = "zomorodmelal.ir" if spec["group"] == "IR" else "mojplaywin.com"
    order = {
        "schema": SCHEMA, "origin": ORIGIN, "source_product_id": ident,
        "source_sha256": sha(spec), "priority": "P0",
        "priority_rank": rank, "priority_group": "OWNER_EDUCATION700",
        "priority_reason": "OWNER_DIRECTIVE_2026_10_24",
        "family_id": "F07", "related_learning_family": "F01",
        "phase": "verified_curriculum_and_original_educational_book_authoring",
        "slot": 1, "subject": spec["title"],
        "instruction": (
            "Produce ONE genuine, original, country-specific supplementary learning "
            "book or workbook based on the named jurisdiction and level. Obtain and "
            "archive the current official curricular scope before authoring; adapt "
            "to school stream, grade, accessibility and student age. Never assume "
            "Europe, USA or GCC shares a universal national curriculum. Author "
            "at least 100000 verified original substantive words in the target "
            "language across appropriate age-friendly student chapters, full "
            "worked solutions and educator notes; no filler, plagiarized textbook "
            "reproduction, synthetic citations, invented exercises/solutions or "
            "unsupported official endorsement. Localize title with a native "
            "reviewer when native_title_verified is false. Track every real "
            "chapter, fact, test and independent review receipt privately."
        ),
        "curriculum_scope": spec, "editions": [{
            "locale": locale, "site": site, "education_page": "education",
            "title_working": spec["title"], "country": spec["country"],
            "national_or_regional_scope": spec["jurisdiction"],
            "currency": "IRR" if spec["group"] == "IR" else "USD",
            "target_language_native_review_required": True,
        }],
        "minimum_original_prose_words": MIN_ORIGINAL_WORDS,
        "authoring_target_original_words": 105_000,
        "required_chapters": 20, "actual_chapters_verified": 0,
        "curriculum_verified": False, "originality_verified": False,
        "fulltext_rights_verified": False, "independent_qc1000_verified": False,
        "end_to_end_buyer_purchase_delivery_verified": False,
        "pricing_authority": "CHATGPT_FAIR_BASE_PRICE_SUBJECT_TO_REVIEW",
        "discount_authority": "OWNER_ONLY", "discount_percent": 0,
        "acceptance": [
            "Verify current official syllabus, jurisdiction, grade and course with source URL, snapshot and date",
            "Independently author at least 100000 meaningful nonduplicated words in selling language; no padding",
            "Use solved worked problems, accurate answer keys, progressive difficulty and age-appropriate learner tasks",
            "Document rights, source-by-claim provenance, pedagogy, accessible layout and native language review",
            "Prove correct original files, validated PDF rendering, classroom use checks and independent QC1000",
            "Before any public listing prove real checkout, invoice, authorized buyer download and email delivery",
            "Discount is zero until owner personally approves a specific promotion"
        ],
        "product_goal_count": 1, "technical_product_release": False,
        "status": "issued", "instruction_kind": "private_factory_work_order",
        "independent_of_websites": True, "requires_customer_order": False,
        "api_required": False, "manufacturing_qa_passed": False,
        "publication_approved": False, "public_distribution_allowed": False,
        "warehouse_goods_created": False, "commercial_release": False,
    }
    order["fingerprint"] = sha({
        k: v for k, v in order.items()
        if k not in ("schema", "status", "instruction_kind", "fingerprint")
    })
    return order


def safe_dir(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("EDUCATION_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("EDUCATION_UNSAFE_DIRECTORY")


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError("EDUCATION_UNSAFE_OLD_ORDER")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("EDUCATION_BAD_JSON")
    return data


def atomic_new(path: Path, data: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("EDUCATION_ORDER_DESTINATION_EXISTS")
    safe_dir(path.parent)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".edu700-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, 0o600)
        if path.exists() or path.is_symlink():
            raise ValueError("EDUCATION_ORDER_COLLISION")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(factory_private: Path) -> dict:
    root = Path(factory_private).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("EDUCATION_FACTORY_ROOT_UNSAFE")
    rows = source_specs()
    area = root / "production-instructions"
    orders_dir = area / "orders"
    safe_dir(area)
    safe_dir(orders_dir)
    lock_path = area / ".orders.lock"
    if lock_path.is_symlink():
        raise ValueError("EDUCATION_UNSAFE_QUEUE_LOCK")
    with lock_path.open("a+b") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old = []
        for path in sorted(orders_dir.iterdir()):
            if path.is_symlink() or not path.is_file() or not ORDER_RE.fullmatch(path.name):
                raise ValueError("EDUCATION_UNEXPECTED_OLD_QUEUE_ENTRY")
            order = read_json(path)
            if (order.get("schema") != SCHEMA or order.get("id") != path.stem
                    or order.get("public_distribution_allowed") is not False
                    or order.get("status") not in (
                        "issued", "in_engineering", "blocked_rework", "completed_verified")
                    or not HEX.fullmatch(str(order.get("fingerprint", "")))):
                raise ValueError("EDUCATION_INVALID_EXISTING_ORDER")
            old.append(order)
        if len(old) + 700 > 15_000:
            raise ValueError("EDUCATION_QUEUE_CAPACITY_EXCEEDED")
        existing = {}
        for order in old:
            if order.get("origin") == ORIGIN:
                ident = order.get("source_product_id")
                if ident in existing:
                    raise ValueError("EDUCATION_DUPLICATE_EXISTING_ID")
                existing[ident] = order
        expected = {
            r["id"]: make_order(r, rank) for rank, r in enumerate(rows, 1)
        }
        for ident, order in existing.items():
            if ident not in expected or any(
                order.get(k) != v for k, v in expected[ident].items()
                if k not in ("id", "status", "created_utc")
            ):
                raise ValueError("EDUCATION_IMMUTABLE_EXISTING_CONFLICT:" + str(ident))
        serial = max((int(x["id"].split("-")[1]) for x in old), default=0)
        created = 0
        for spec in rows:
            ident = spec["id"]
            if ident in existing:
                continue
            serial += 1
            record = dict(expected[ident], id="WO-%08d" % serial)
            atomic_new(orders_dir / (record["id"] + ".json"), record)
            existing[ident] = record
            created += 1
        ranked = [existing[spec["id"]]["id"] for spec in rows]
        index_path = area / "owner-education700-p0-index.json"
        index = {
            "schema": INDEX_SCHEMA, "origin": ORIGIN,
            "status": "P0_REGISTERED_PENDING_REAL_AUTHORING",
            "requested_books": 700, "minimum_total_original_words": 70_000_000,
            "regional_allocation": COUNTS, "order_ids_ranked": ranked,
            "catalog_sha256": sha({"specs": rows}),
            "price_discounts_authorized": False,
            "actual_manuscripts_completed": 0, "independently_approved": 0,
            "commercial_release": False, "website_changes": 0,
        }
        if index_path.exists():
            if read_json(index_path) != index:
                raise ValueError("EDUCATION_EXISTING_INDEX_CONFLICT")
        else:
            atomic_new(index_path, index)
    return {
        "created": created, "registered": len(ranked),
        "per_region": COUNTS, "target_original_prose_words": 70_000_000,
        "books_authored_and_approved": 0, "published": 0,
        "index_path": str(index_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private")
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args()
    if arguments.selftest:
        rows = source_specs()
        assert len(rows) == 700
        assert len({r["title"] for r in rows}) == 700
        assert all(make_order(r, i)["public_distribution_allowed"] is False
                   for i, r in enumerate(rows, 1))
        print("EDUCATION700_CONTRACT_SELFTEST=PASS")
        return
    if not arguments.factory_private:
        parser.error("--factory-private required unless --selftest")
    print(json.dumps(install(Path(arguments.factory_private)),
                     sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()

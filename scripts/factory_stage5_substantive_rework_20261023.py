#!/usr/bin/env python3
"""Private Stage-5 evidence-specific revision packets from Stage-6 rework orders.

A complete agronomy manual needs qualified authors and original full-text checks.
This offline worker produces immutable, source-specific bilingual revision briefs,
not invented agricultural findings or a human review/QA approval. No site writes.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

SCHEMA = "saeit.factory.stage5.substantive-revision-brief.v1"
REVIEW_SCHEMA = "saeit.factory.stage6.substantive-review-inbox.v1"
MAX_BODY = 400000
LOCALES = ("fa-IR", "en-US")

def load(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("STAGE5_REWORK_UNSAFE_DEPENDENCY")
    spec = importlib.util.spec_from_file_location(label, str(path))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def tidy(value, limit=1000):
    if not isinstance(value, str):
        raise ValueError("STAGE5_REWORK_NOT_TEXT")
    value = " ".join(value.replace("\x00", " ").split())
    if not value or len(value) > limit:
        raise ValueError("STAGE5_REWORK_INVALID_TEXT")
    return value.replace("<", "&lt;").replace(">", "&gt;")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def checked_packet(area, name, lib, stage5, stage6):
    handoff, prototype, design, research, order, editions = stage5.verified_stage4(area, name, lib)
    manifest = lib.read(area / "stage-05/completed-drafts" / name)
    request = lib.read(area / "stage-05/substantive-rework-inbox" / name)
    preflight = lib.read(area / "stage-06/technical-preflight" / name)
    if (request.get("schema") != stage6.REWORK
            or request.get("order_id") != handoff["order_id"]
            or request.get("revision_under_review") != handoff["revision"]
            or request.get("stage6_preflight_sha256") != lib.digest(preflight)
            or request.get("status") != "awaiting_substantive_reauthoring"
            or preflight.get("schema") != stage6.REPORT
            or preflight.get("integrity_preflight_passed") is not True
            or preflight.get("stage5_manifest_sha256") != lib.digest(manifest)
            or preflight.get("stage2_research_sha256") != lib.digest(research)
            or manifest.get("schema") != stage5.SCHEMA
            or manifest.get("draft_kind") != "original_bilingual_evidence_method_workbook"):
        raise RuntimeError("STAGE5_REWORK_UNVERIFIED_REQUEST_CHAIN")
    if not isinstance(research.get("sources"), list) or len(research["sources"]) < 4:
        raise RuntimeError("STAGE5_REWORK_TOO_FEW_SOURCES")
    if not isinstance(research.get("claims"), list) or len(research["claims"]) < 5:
        raise RuntimeError("STAGE5_REWORK_TOO_FEW_CLAIMS")
    sources = {x["id"]: x for x in research["sources"]}
    claims = {x["id"]: x for x in research["claims"]}
    if len(sources) != len(research["sources"]) or len(claims) != len(research["claims"]):
        raise RuntimeError("STAGE5_REWORK_DUPLICATE_EVIDENCE")
    if len(design["chapters"]) < 5:
        raise RuntimeError("STAGE5_REWORK_TOO_FEW_CHAPTERS")
    for unit in design["chapters"]:
        claim = claims.get(unit["source_claim_id"])
        if claim is None or not set(unit["source_ids"]) == set(claim["source_ids"]):
            raise RuntimeError("STAGE5_REWORK_CLAIM_MISMATCH")
        if not set(claim["source_ids"]).issubset(sources):
            raise RuntimeError("STAGE5_REWORK_UNLINKED_SOURCE")
        claimed = claim.get("indexed_sentence_sha256")
        if claimed is not None and claimed != sha(claim["statement"].encode("utf-8")):
            raise RuntimeError("STAGE5_REWORK_CLAIM_SHA_MISMATCH")
    for loc in LOCALES:
        original = stage6.checked_read(
            area / "stage-05/drafts", name, loc, manifest["manuscript_sha256"][loc])
        if len(original.split()) < stage6.MIN_WORDS:
            raise RuntimeError("STAGE5_REWORK_ORIGINAL_DRAFT_INVALID")
    for obj in (manifest, request, preflight, research):
        lib.deny_approval(obj)
    return manifest, design, research, order, editions, sources, claims

def make_brief(design, research, editions, sources, claims, locale):
    title = tidy(editions[locale]["title"], 300)
    audience = tidy(editions[locale]["audience"], 300)
    scope = tidy(research["locale_scopes"][locale], 2000)
    fa = locale == "fa-IR"
    lines = [
        "# " + title, "",
        ("## نسخه دوم: پرونده بازنویسی مبتنی بر منابع علمی" if fa
         else "## Revision 2: Source-specific scientific reauthoring dossier"), "",
        ("مخاطب: " if fa else "Audience: ") + audience, "",
        ("محدوده و محدودیت انتقال: " if fa else "Scope and transfer limits: ") + scope, "",
        ("پیش‌نویس خصوصی؛ متن کامل منابع و انطباق با ایران هنوز بررسی مستقل نشده‌اند."
         if fa else "Private revision brief: primary full texts and local validity remain unverified."), "",
    ]
    for unit in design["chapters"]:
        claim = claims[unit["source_claim_id"]]
        label = tidy(unit["title_fa" if fa else "title_en"], 280)
        n = unit["unit"]
        lines += [("## فصل " if fa else "## Chapter ") + str(n) + ": " + label, ""]
        lines += [
            ("### موضوع تخصصی و شاهد دقیق" if fa else "### Topic-specific indexed evidence"), "",
            ("موضوع مورد بررسی: " if fa else "Investigation focus: ") + label + " / " + title, "",
            ("متن انگلیسی استخراج‌شده از چکیده نمایه‌شده، بدون ترجمه ادعایی:"
             if fa else "Exact indexed-abstract claim; not yet checked against primary publication:"), "",
            "> " + tidy(claim["statement"], 1800), ""
        ]
        for source_id in claim["source_ids"]:
            s = sources[source_id]
            lines += [
                ("منبع " if fa else "Source ") + tidy(source_id, 90) + ": " +
                tidy(s["title"], 450) + " — " + tidy(s["publisher"], 220), "",
                ("پیوند مرجع: " if fa else "Publisher page: ") + tidy(s["url"], 600), ""
            ]
            if s.get("doi"):
                lines.append("DOI: " + tidy(s["doi"], 260))
            if s.get("publication_year"):
                lines.append(("سال: " if fa else "Year: ") + str(s["publication_year"]))
        if fa:
            lines += [
                "", "### تکلیف موضوعی بازنویسی", "",
                "۱. ادعای بالا را در متن اصلی مقاله پیدا کنید؛ متغیرهای مرتبط با «" + label + "» را عیناً ثبت کنید.",
                "۲. معلوم کنید مطالعه واقعاً درباره همین موضوع و گروه هدف کتاب بوده است یا فقط ارتباط غیرمستقیم دارد.",
                "۳. طراحی آزمایش، جمعیت، اقلیم، دامنه و واحد اندازه‌گیری را از متن منبع استخراج کنید.",
                "۴. یافته گزارش‌شده و تفسیر نویسندگان را جداگانه با شماره صفحه یادداشت کنید.",
                "۵. برای کاربرد در ایران، تفاوت اقلیم، خاک، ارقام، تجهیزات و مقررات مرتبط را بررسی کنید.",
                "۶. اگر داده متن کامل موجود نیست، خانه جدول را «نامعلوم» بگذارید؛ مقدار و اثر نسازید.",
                "", "### تمرین تحلیلی و پاسخ", "",
                "پرسش: آیا همین جمله نمایه‌شده برای ارائه یک دستور اجرایی در زمینه «" + label + "» کافی است؟",
                "پاسخ: خیر؛ نتیجه تا زمانی که روش، مقایسه، محدودیت‌ها و ایمنی از مقاله اصلی احراز نشده‌اند، فقط شاهد مقدماتی است.",
                "", "### مشخصات لازم برای ویراستار و داور", "",
                "گزاره | DOI | صفحه متن کامل | متغیر و واحد | روش | حد عدم قطعیت | قابلیت کاربرد محلی | شاهد تأیید تخصصی.", ""
            ]
        else:
            lines += [
                "", "### Subject-specific reauthoring assignment", "",
                "1. Locate the passage in the full paper and record variables specifically about '" + label + "'.",
                "2. Check whether the sampled population and outcome actually match the book's named subject.",
                "3. Extract study design, population, climate, timeframe and measurement units from the primary text.",
                "4. Separate reported findings from the authors' interpretation; cite exact full-text pages.",
                "5. Assess transferability to the intended audience, including safety and applicable local rules.",
                "6. If a full-text value is unavailable, mark it unknown. Do not invent an effect size or field outcome.",
                "", "### Evidence-based assessment and key", "",
                "Question: Does the indexed excerpt alone support an operational recommendation for '" + label + "'?",
                "Answer: No. Verify methods, comparisons, limitations and safety using primary evidence first.",
                "", "### Editorial and reviewer evidence record", "",
                "Claim | DOI | Full-text page | Variable/unit | Study design | Uncertainty | Local validity | Reviewer attestation.", ""
            ]
    lines += [
        ("## فهرست منابع و کارهای باقی‌مانده" if fa else "## Reference ledger and outstanding work"), "",
    ]
    for src in research["sources"]:
        lines += ["- [" + tidy(src["id"], 90) + "] " + tidy(src["title"], 450) +
                  " — " + tidy(src["publisher"], 220) + " (" + tidy(src["url"], 600) + ")"]
    lines += ["", ("الزام باقی‌مانده: تألیف تخصصی متن کامل، بررسی اصل منابع، بازبینی مستقل فارسی و انگلیسی و آزمون میدانی."
                  if fa else "Still required: complete specialist manuscript, original-source inspection, independent bilingual review and field evaluation."),
              "", "QA1000: NOT APPROVED. Publication: PROHIBITED.", ""]
    body = "\n".join(lines)
    if len(body.encode("utf-8")) > MAX_BODY or len(body.split()) < 600:
        raise RuntimeError("STAGE5_REWORK_BRIEF_BOUNDS")
    return body.encode("utf-8")

def reauthor(area, name, lib, stage5, stage6):
    original, design, research, order, editions, sources, claims = checked_packet(
        area, name, lib, stage5, stage6)
    files = {loc: make_brief(design, research, editions, sources, claims, loc) for loc in LOCALES}
    root = area / "stage-05/substantive-revisions" / name[:-5] / "v002"
    if root.is_symlink():
        raise RuntimeError("STAGE5_REWORK_UNSAFE_REVISION_DIR")
    for loc, body in files.items():
        stage5.write_once(root / (loc + ".md"), body, lib)
    manifest = {
        "schema": SCHEMA, "order_id": original["order_id"],
        "source_order_revision": original["revision"], "manuscript_revision": 2,
        "stage5_original_manifest_sha256": lib.digest(original),
        "stage2_research_sha256": lib.digest(research),
        "manuscript_sha256": {loc: sha(body) for loc, body in files.items()},
        "source_claim_ids": [c["id"] for c in research["claims"]],
        "source_ids": [s["id"] for s in research["sources"]],
        "content_kind": "source_specific_revision_brief_not_complete_agronomy_manual",
        "substantive_full_text_authoring_completed": False,
        "original_fulltext_verified": False,
        "independent_scientific_review": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False}
    review = {
        "schema": REVIEW_SCHEMA, "order_id": original["order_id"],
        "source_order_revision": original["revision"], "manuscript_revision": 2,
        "revision_manifest_sha256": lib.digest(manifest),
        "status": "awaiting_qualified_domain_author_and_independent_review",
        "full_text_source_extraction_required": True,
        "bilingual_topic_manuscript_required": True,
        "reviewer_signature_created": False,
        "quality1000_approved": False, "public_distribution_allowed": False}
    created = lib.once(area / "stage-05/substantive-revision-manifests" / name, manifest)
    lib.once(area / "stage-06/substantive-review-inbox" / name, review)
    return created

def execute(root, lib, stage5, stage6, batch=200):
    root = Path(root).expanduser().resolve()
    area = root / "production-instructions"
    if not root.is_dir():
        raise RuntimeError("STAGE5_REWORK_PRIVATE_ROOT_MISSING")
    lib.private_dir(area / "stage-05/substantive-revision-manifests")
    lib.private_dir(area / "stage-06/substantive-review-inbox")
    lib.private_dir(area / "stage-05/substantive-revision-blocked")
    queue = area / "stage-05/substantive-rework-inbox"
    if queue.is_symlink() or not queue.is_dir():
        raise RuntimeError("STAGE5_REWORK_QUEUE_UNSAFE")
    lock = area / ".stage5-substantive-revision.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE5_REWORK_LOCK_UNSAFE")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        names = sorted(p.name for p in queue.iterdir() if
                       p.is_file() and not p.is_symlink() and lib.NAME.fullmatch(p.name))
        cursor_path = area / "stage-05/substantive-revision-cursor.json"
        if cursor_path.is_symlink():
            raise RuntimeError("STAGE5_REWORK_CURSOR_UNSAFE")
        cursor = lib.read(cursor_path) if cursor_path.exists() else {
            "schema": "saeit.factory.stage5.substantive-cursor.v1", "next_index": 0}
        if (cursor.get("schema") != "saeit.factory.stage5.substantive-cursor.v1"
                or type(cursor.get("next_index")) is not int or cursor["next_index"] < 0):
            raise RuntimeError("STAGE5_REWORK_CURSOR_INVALID")
        count = min(batch, len(names))
        start = cursor["next_index"] % len(names) if names else 0
        selected = [names[(start + i) % len(names)] for i in range(count)]
        made = blocked = 0
        for name in selected:
            try:
                made += int(reauthor(area, name, lib, stage5, stage6))
            except (RuntimeError, ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
                blocked += 1
                lib.atomic(area / "stage-05/substantive-revision-blocked" / name, {
                    "order_file": name,
                    "reason": type(exc).__name__ + ":" + str(exc)[:160],
                    "review_approval_created": False})
        lib.atomic(cursor_path, {
            "schema": "saeit.factory.stage5.substantive-cursor.v1",
            "next_index": (start + count) % len(names) if names else 0})
        result = {
            "rework_orders": len(names), "attempted": count,
            "source_specific_revision_briefs_created_this_run": made,
            "source_specific_revision_briefs_total": len(list(
                (area / "stage-05/substantive-revision-manifests").glob("WO-*.json"))),
            "blocked_this_run": blocked,
            "qualified_domain_author_approvals": 0,
            "independent_specialist_approvals": 0,
            "stage7_handoffs": 0, "qa1000_approvals": 0,
            "sites_changed": False}
        lib.atomic(area / "stage-05/substantive-revision-status.json", result)
        return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--stage34-worker", required=True)
    p.add_argument("--stage5-worker", required=True)
    p.add_argument("--stage6-worker", required=True)
    p.add_argument("--batch", type=int, default=200)
    a = p.parse_args()
    if not 1 <= a.batch <= 1000:
        raise SystemExit("STAGE5_REWORK_BAD_BATCH")
    lib = load(a.stage34_worker, "stage34_substantive_rework")
    stage5 = load(a.stage5_worker, "stage5_substantive_rework")
    stage6 = load(a.stage6_worker, "stage6_substantive_rework")
    print(json.dumps(execute(a.factory_private, lib, stage5, stage6, a.batch),
                     ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("STAGE5_SUBSTANTIVE_REWORK_ERROR=" +
              type(error).__name__ + ":" + str(error)[:160], file=sys.stderr)
        raise SystemExit(1)

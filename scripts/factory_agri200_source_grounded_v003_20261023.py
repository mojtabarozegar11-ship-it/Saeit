#!/usr/bin/env python3
"""Produce immutable *new* source-specific bilingual teaching editions from QC returns.

Grounded only in independently indexed metadata/abstract statements and the
already-verified Stage2->5 hash chain. No fabricated agronomic findings or
human specialist signatures; this does not assert commercial QC1000 approval.
"""
import argparse
import fcntl
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = "saeit.factory.agri200.source-grounded-v003.v1"
NAME = re.compile(r"WO-[0-9]{8}--r001\.json\Z")
MAX = 700_000
LOCALES = ("fa-IR", "en-US")


def load_module(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("REVISION_DEPENDENCY_UNSAFE")
    spec = importlib.util.spec_from_file_location(label, str(path))
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prose(value, limit=800):
    if not isinstance(value, str):
        raise RuntimeError("SOURCE_TEXT_NOT_STRING")
    item = " ".join(value.replace("\0", " ").split()).strip()
    if not item or len(item) > limit:
        raise RuntimeError("SOURCE_TEXT_BOUNDS")
    return item.replace("<", "&lt;").replace(">", "&gt;")


def catalog(area, name, lib, stage5):
    handoff, prototype, design, research, order, editions = stage5.verified_stage4(area, name, lib)
    original = lib.read(area / "stage-05/completed-drafts" / name)
    qc = lib.read(area / "stage-06/strict-qc1000" / name)
    repair = lib.read(area / "stage-05/strict-qc-rework" / name)
    if (original.get("stage") != 5 or original.get("revision") != 1
            or original.get("stage4_prototype_sha256") != lib.digest(prototype)
            or original.get("stage2_research_sha256") != lib.digest(research)
            or original.get("draft_kind") != "original_bilingual_evidence_method_workbook"
            or qc.get("stage5_manifest_sha256") != lib.digest(original)
            or repair.get("stage5_manifest_sha256") != lib.digest(original)
            or repair.get("strict_qc_report_sha256") != lib.digest(qc)
            or repair.get("must_resubmit_new_artifact_and_repeat_strict_qc") is not True
            or qc.get("quality1000_approved") is not False
            or qc.get("commercial_release") is not False):
        raise RuntimeError("REVISION_QC_EVIDENCE_CHAIN_FAILED")
    sources = {s["id"]: s for s in research["sources"]}
    claims = {c["id"]: c for c in research["claims"]}
    if (len(sources) < 4 or len(claims) < 5
            or len(sources) != len(research["sources"])
            or len(claims) != len(research["claims"])
            or len(design["chapters"]) < 5):
        raise RuntimeError("REVISION_INSUFFICIENT_PRIMARY_EVIDENCE")
    for unit in design["chapters"]:
        claim = claims.get(unit["source_claim_id"])
        if not claim or set(unit["source_ids"]) != set(claim["source_ids"]):
            raise RuntimeError("REVISION_UNLINKED_CHAPTER")
        if not set(unit["source_ids"]).issubset(sources):
            raise RuntimeError("REVISION_UNLINKED_BIBLIOGRAPHY")
    return design, research, editions, original, repair, sources, claims


def edition(design, research, editions, sources, claims, locale):
    fa = locale == "fa-IR"
    title = prose(editions[locale]["title"], 300)
    audience = prose(editions[locale]["audience"], 250)
    scope = prose(research["locale_scopes"][locale], 2200)
    lines = [
        "# " + title, "",
        ("## نسخه پژوهشی بازنگری‌شده — مجموعه آموزشی اختصاصی" if fa
         else "## Revised research edition — subject-specific learning companion"), "",
        ("مخاطب: " if fa else "Audience: ") + audience, "",
        ("دامنه شواهد و محدودیت انتقال: " if fa else "Evidence scope and transfer bounds: ") + scope, "",
        ("این تألیف از داده‌های کتابشناختی و گزاره‌های چکیده‌های علمی نمایه‌شده ساخته شده است. "
         "هیچ نتیجه آزمایشگاهی یا مزرعه‌ای و هیچ دستور مصرف نهاده از خود اختراع نشده است. "
         "برای تصمیم اجرایی، متن کامل مقاله و شرایط محلی باید مستقل بررسی شوند."
         if fa else
         "This original educational companion organizes traceable indexed scientific abstract statements. "
         "No field measurements, experimental effect sizes or chemical application instructions are invented. "
         "Read the full primary studies and obtain locality-specific checks before acting."), "",
    ]
    for unit in design["chapters"]:
        num = unit["unit"]
        label = prose(unit["title_fa" if fa else "title_en"], 300)
        claim = claims[unit["source_claim_id"]]
        statement = prose(claim["statement"], 1800)
        ids = sorted(unit["source_ids"])
        citations = ", ".join(ids)
        lines += [
            ("## فصل " if fa else "## Chapter ") + str(num) + ": " + label, "",
            ("### مسئله علمی اختصاصی فصل" if fa else "### The chapter's defined research question"), "",
            (f"این فصل رابطهٔ «{label}» را در چارچوب موضوع «{title}» بررسی می‌کند. "
             f"ملاک پژوهش، گزارهٔ قابل‌ردیابی با شناسهٔ {prose(claim['id'],90)} "
             f"و پیوند به منابع {citations} است. این گزاره مدرک اولیه است و برای تعیین نتیجه عملی کافی نیست."
             if fa else
             f"This chapter tests how the indexed statement associated with '{label}' informs '{title}'. "
             f"The actual starting point is traceable claim {prose(claim['id'],90)}, linked to {citations}. "
             "Treat it as an indexed research statement, not a verified practical prescription."), "",
            ("### گزارهٔ چکیدهٔ نمایه‌شده" if fa else "### Exact indexed research statement"), "",
            "> " + statement, "",
            ("### نقشهٔ اسناد و قابلیت راستی‌آزمایی" if fa else "### Source traceability and verification map"), "",
        ]
        for sid in ids:
            source = sources[sid]
            source_name = prose(source["title"], 500)
            publisher = prose(source["publisher"], 220)
            url = prose(source["url"], 650)
            year = source.get("publication_year")
            doi = source.get("doi")
            lines += [
                f"- **{sid}** — {source_name}; {publisher}; " +
                (("سال " if fa else "year ") + str(year) + "; " if year else "") +
                (("DOI " + prose(doi,250) + "; ") if doi else "") + url,
            ]
        lines += [""]
        if fa:
            lines += [
                "### تحلیل علمی، مجهولات و مرزبندی ادعا", "",
                f"برای ارزیابی گزارهٔ «{label}»، ابتدا نوع مطالعه و گروه نمونه را در منابع {citations} ثبت کنید. "
                f"سپس متغیر نتیجه و واحد اندازه‌گیری مرتبط با {label} را از متن اصلی استخراج کنید. "
                "در دادهٔ حاضر، اثر کمی، جهت علیت و دامنه عدم قطعیت به‌طور مستقل اثبات نشده‌اند؛ "
                "خالی گذاشتن نتیجه بهتر از ساختن یک عدد است.", "",
                f"برای کاربرد احتمالیِ نتایج فصل {num} در کشاورزی ایران، سازگاری اقلیم، خاک، ژنوتیپ، "
                f"سامانه مدیریت و مقررات را جداگانه بیازمایید. در موضوع {label} هر تفاوت شرایط می‌تواند "
                "موجب شکست تعمیم باشد. این بند روش ارزیابی است، نه توصیه به مصرف یا مداخله.", "",
                "### فعالیت کاربردی مبتنی بر سند", "",
                f"۱. منبع {ids[0]} را در نسخهٔ اصلی باز کنید و صفحهٔ مربوط به «{label}» را بیابید.",
                f"۲. برای گزارهٔ {prose(claim['id'],90)}، متن یافته و تفسیر نویسندگان را در دو ستون مستقل بنویسید.",
                f"۳. مشخص کنید ابزار سنجش، گروه مقایسه و دوره بررسی در فصل {num} چه بوده‌اند.",
                f"۴. یک فهرست از محدودیت‌های انتقال نتیجهٔ «{label}» به مزرعهٔ واقعی تهیه کنید.",
                "۵. تنها یک مشاهدهٔ غیرمخرب و بدون مداخله خطرناک طرح کنید؛ مقدار مشاهده‌شده را بعداً ثبت کنید.",
                "۶. اگر متن کامل منبع دسترس‌پذیر نیست، وضعیت را «نیازمند شواهد» علامت بزنید.", "",
                "### برگهٔ کار آماده برای استفاده", "",
                f"| شاخص مربوط به {label} | شاهد/صفحه اصل منبع | شرایط مکانی | مقدار با واحد | عدم قطعیت | نتیجه قابل دفاع |",
                "|---|---|---|---|---|---|",
                f"| بررسی ادعای {prose(claim['id'],90)} | تکمیل شود | تکمیل شود | نامعلوم | نامعلوم | در انتظار بررسی |", "",
                "### آزمون درک مطلب و پاسخ مستدل", "",
                f"- پرسش: آیا گزارهٔ {prose(claim['id'],90)} به‌تنهایی اجرای توصیه‌ای درباره «{label}» را مجاز می‌کند؟",
                f"- پاسخ: خیر. باید طراحی مطالعه، قابلیت کاربرد محلی، ایمنی و اصل متن منابع {citations} احراز شوند.",
                f"- پرسش: اگر نتایج دو منبع دربارهٔ فصل {num} با یکدیگر ناسازگار باشند، چه می‌کنیم؟",
                "- پاسخ: تفاوت جمعیت نمونه، محیط، روش، کیفیت سنجش و عدم قطعیت را بررسی و اختلاف را مستند می‌کنیم.", "",
            ]
        else:
            lines += [
                "### Technical interpretation and what is not yet established", "",
                f"To assess '{label}', inspect the primary study designs behind sources {citations}. "
                f"Extract measured outcomes, units and sample populations specifically applicable to {label}. "
                "The indexed packet does not independently establish an intervention effect, "
                "the causal direction or a confidence interval; absent values remain unknown.", "",
                f"Transferability for chapter {num} depends on location, climate, soil, "
                f"genotype, instrumentation, management history and local rules. "
                f"A different study setting can invalidate a presumed transfer about '{label}'. "
                "This is a risk checklist, not an agronomic application recommendation.", "",
                "### Traceable practical research activity", "",
                f"1. Retrieve the original publication for {ids[0]} and locate the passage about '{label}'.",
                f"2. Separate the observed result from interpretation for claim {prose(claim['id'],90)}.",
                f"3. Record sampling, the comparator, the measurement instrument and study duration of chapter {num}.",
                f"4. Enumerate the local restrictions before using findings associated with '{label}'.",
                "5. Create only a non-destructive field observation protocol with explicit stop criteria.",
                "6. Mark full-text unavailability as missing evidence; never make up an effect size.", "",
                "### Reusable source-to-observation worksheet", "",
                f"| Measure relevant to {label} | Full-text page | Study locality | Units/value | Uncertainty | Defensible inference |",
                "|---|---|---|---|---|---|",
                f"| Claim {prose(claim['id'],90)} | To verify | To record | Unknown | Unknown | Needs primary-text check |", "",
                "### Self-assessment and justified answers", "",
                f"- Question: Can claim {prose(claim['id'],90)} alone justify an operational decision for '{label}'?",
                f"- Answer: No. Original sources {citations}, study design, safety and locality must be checked.",
                f"- Question: How should disagreement among chapter {num}'s publications be handled?",
                "- Answer: Compare populations, methods, baseline risks, measurement validity and uncertainty before interpreting disagreements.", "",
            ]
    lines += [
        ("## فهرست منابع پژوهشی" if fa else "## Indexed scientific references"), ""
    ]
    for src in research["sources"]:
        lines.append("- " + prose(src["id"], 100) + ": " +
                     prose(src["title"], 500) + " — " +
                     prose(src["publisher"], 250) + "; " +
                     prose(src["url"], 650))
    lines += [
        "", ("## وضعیت کنترل کیفیت و حدود استفاده" if fa else "## Quality and use boundaries"), "",
        ("ارزیابی مستقل متن کامل، اصالت و صحت یافته‌ها، آزمون میدانی، انطباق مقرراتی و تأیید امضاشدهٔ متخصص باقی است. "
         "این نسخهٔ جدید محصول آموزشی پژوهشیِ خصوصی است و برای فروش عمومی یا توصیه حرفه‌ای تأیید نشده است."
         if fa else
         "Independent full-text verification, scientific accuracy review, actual field testing, "
         "local-regulatory checks and authenticated specialist approval remain outstanding. "
         "This revised learning artifact is private and not approved for public sale or professional prescriptions."),
        "", "QC1000: PENDING INDEPENDENT REVIEW. PUBLIC SALE: NOT AUTHORIZED.", ""
    ]
    text = "\n".join(lines)
    if len(text.split()) < 1200 or len(text.encode("utf-8")) > MAX:
        raise RuntimeError("REVISION_MANUSCRIPT_SIZE_INVALID")
    paragraphs = [re.sub(r"\s+", " ", p).strip().casefold()
                  for p in re.split(r"\n\s*\n", text) if len(p.split()) >= 20]
    fraction = (len(paragraphs) - len(set(paragraphs))) / len(paragraphs) if paragraphs else 1
    if fraction > 0.1:
        raise RuntimeError("REVISION_REPEATED_CONTENT")
    return text.encode("utf-8")


def author_one(area, name, lib, stage5, candidate):
    if not NAME.fullmatch(name):
        raise RuntimeError("REVISION_INVALID_ID")
    design, research, editions, old, ticket, sources, claims = catalog(area, name, lib, stage5)
    drafts = {loc: edition(design, research, editions, sources, claims, loc) for loc in LOCALES}
    base = area / "stage-05/source-grounded-v003" / name[:-5]
    source_json = [{key: src.get(key) for key in (
        "id", "title", "publisher", "url", "doi", "publication_year")}
        for src in research["sources"]]
    data = {
        "fa-IR.md": drafts["fa-IR"], "en-US.md": drafts["en-US"],
        "sources.json": (json.dumps(source_json, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
        "README.md": ("# Bilingual evidence-linked agricultural learning companion (v003)\n"
                      "Evidence-indexed private educational edition. No invented findings. "
                      "Full-text scientific checks, safety certification and independent QC1000 "
                      "remain outstanding; not ready for sale.\n").encode(),
    }
    doc = "<!doctype html><html lang='en'><meta charset='utf-8'><title>" + html.escape(
        editions["en-US"]["title"], quote=True) + "</title><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{max-width:920px;margin:auto;padding:2rem;font-family:system-ui;line-height:1.6}button{padding:.6rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit}</style><button id='toggle'>فارسی / English</button><pre id='body'></pre><script>" + (
            "const manuscripts=" + candidate.data_script({loc: drafts[loc].decode("utf8") for loc in LOCALES}) + ";"
            "let loc='fa-IR';let pane=document.getElementById('body');"
            "function render(){pane.textContent=manuscripts[loc];document.documentElement.lang=loc.slice(0,2);"
            "document.documentElement.dir=loc==='fa-IR'?'rtl':'ltr'}"
            "document.getElementById('toggle').onclick=()=>{loc=loc==='fa-IR'?'en-US':'fa-IR';render()};render();"
        ) + "</script></html>"
    data["index.html"] = doc.encode("utf8")
    prior_hash = lib.digest(old)
    ticket_hash = lib.digest(ticket)
    data["integrity.json"] = (json.dumps({
        "schema": SCHEMA, "original_stage5_sha256": prior_hash,
        "strict_qc_rework_sha256": ticket_hash,
        "file_sha256": {key: sha(value) for key, value in sorted(data.items())},
        "revision": 3, "independent_qc1000_approved": False,
        "public_distribution_allowed": False,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    archive = candidate.reproducible_zip(data, "agri-" + name[:-5] + "-v003")
    digest = sha(archive)
    manuscript_hashes = {loc: sha(drafts[loc]) for loc in LOCALES}
    lib.private_dir(base)
    for loc, body in drafts.items():
        stage5.write_once(base / (loc + ".md"), body, lib)
    stage5.write_once(base / ("edition-" + digest + ".zip"), archive, lib)
    manifest = {
        "schema": SCHEMA, "order_file": name, "order_id": old["order_id"],
        "source_revision": 1, "artifact_revision": 3,
        "original_stage5_sha256": prior_hash, "strict_qc_rework_sha256": ticket_hash,
        "stage2_research_sha256": lib.digest(research),
        "source_ids": sorted(sources), "claim_ids": sorted(claims),
        "manuscript_sha256": manuscript_hashes,
        "zip_sha256": digest, "zip_bytes": len(archive),
        "archive_relative_path": str((base / ("edition-" + digest + ".zip")).relative_to(area)),
        "original_bilingual_source_grounded_edition_created": True,
        "primary_fulltexts_independently_verified": False,
        "independent_scientific_review": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False
    }
    return lib.once(area / "stage-05/source-grounded-v003-manifests" / name, manifest)


def run(root, lib, stage5, candidate, *, batch=200, only_order_id=None):
    if only_order_id is not None and (not isinstance(only_order_id,str)
                                   or re.fullmatch(r"WO-[0-9]{8}",only_order_id) is None):
        raise RuntimeError("REVISION_TARGET_ORDER_INVALID")
    area = Path(root).resolve() / "production-instructions"
    inbox = area / "stage-05/strict-qc-rework"
    if inbox.is_symlink() or not inbox.is_dir():
        raise RuntimeError("REVISION_REWORK_INBOX_MISSING")
    for sub in ("stage-05/source-grounded-v003", "stage-05/source-grounded-v003-manifests",
                "stage-05/source-grounded-v003-blocked"):
        lib.private_dir(area / sub)
    lock = area / ".source-grounded-v003.lock"
    if lock.is_symlink():
        raise RuntimeError("REVISION_LOCK_UNSAFE")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        names = sorted(p.name for p in inbox.iterdir()
                       if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
        if only_order_id is not None:
            names = [name for name in names if name.startswith(only_order_id+"--r")]
        created = failed = 0
        for name in names[:batch]:
            try:
                created += int(author_one(area, name, lib, stage5, candidate))
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
                failed += 1
                lib.atomic(area / "stage-05/source-grounded-v003-blocked" / name, {
                    "order_file": name, "error": type(exc).__name__ + ":" + str(exc)[:170],
                    "quality1000_approved": False, "commercial_release": False})
        report = {"input_rework_tickets": len(names), "new_bilingual_v003_editions": created,
                  "attempted_this_tick": min(batch, len(names)), "blocked_this_tick": failed,
                  "private_v003_total": sum(1 for p in (area / "stage-05/source-grounded-v003-manifests").iterdir()
                                            if p.is_file() and NAME.fullmatch(p.name)),
                  "independent_qc1000_approvals": 0, "published_products": 0}
        lib.atomic(area / "stage-05/source-grounded-v003-status.json", report)
        return report


if __name__ == "__main__":
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--factory-private", required=True)
        p.add_argument("--stage34-worker", required=True)
        p.add_argument("--stage5-worker", required=True)
        p.add_argument("--candidate-worker", required=True)
        p.add_argument("--batch", type=int, default=200)
        p.add_argument("--only-order-id")
        args = p.parse_args()
        if not 1 <= args.batch <= 250:
            raise RuntimeError("REVISION_BATCH_INVALID")
        lib = load_module(args.stage34_worker, "revision_stage34")
        stage5 = load_module(args.stage5_worker, "revision_stage5")
        candidate = load_module(args.candidate_worker, "revision_zip")
        print(json.dumps(run(args.factory_private, lib, stage5, candidate, batch=args.batch,
                             only_order_id=args.only_order_id),
                         sort_keys=True, ensure_ascii=False))
    except Exception as exc:
        print("REVISION_ERROR:" + type(exc).__name__ + ":" + str(exc)[:180], file=sys.stderr)
        raise SystemExit(1)

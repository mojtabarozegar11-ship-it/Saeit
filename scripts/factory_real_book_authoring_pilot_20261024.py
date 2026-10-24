#!/usr/bin/env python3
"""Private original book authoring by an owner-configured paid inference backend.

One bounded, budget-reserved chapter part per invocation. No API credential or
owner budget => no charge. This is an original manuscript DRAFT worker, not a
scientific reviewer, QC1000 certification, purchase or publication.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

SCHEMA = "saeit.factory.original-book-authoring.v1"
MODEL_ENDPOINT = "https://api.openai.com/v1/responses"
CHAPTER_COUNT = 20
CHAPTER_TARGET = 5250
BOOK_MINIMUM = 100000
WORD = re.compile(r"[^\W\d_][\w\u200c'-]*", re.UNICODE)
BOOK_ID = re.compile(r"AGRI-[0-9]{3}\Z")
CHUNK_NAME = re.compile(r"chapter-([0-9]{2})-part-([0-9]{3})\.md\Z")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def tokens(prose):
    # Never count headings, citations, URLs, code fences or reference lists.
    lines = []
    refs = False
    fenced = False
    for line in prose.splitlines():
        v = line.strip()
        if v.startswith("```") or v.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced or not v:
            continue
        if v.startswith("## "):
            refs = bool(re.search(r"(references|bibliography|منابع|کتابنامه)", v, re.I))
        if refs or v.startswith(("#", "|", ">", "---", "http://", "https://")):
            continue
        v = re.sub(r"https?://\S+", " ", v)
        lines.append(v)
    return [w.casefold() for w in WORD.findall(" ".join(lines))]


def distinct_enough(text, previous):
    new = tokens(text)
    if len(new) < 600:
        return False, "CHUNK_TOO_SHORT"
    if len(new) > 4500:
        return False, "CHUNK_OVERLONG"
    if len(set(new)) < 120:
        return False, "CHUNK_LEXICAL_PADDING"
    shingles = [tuple(new[i:i+12]) for i in range(0, max(0, len(new)-11), 6)]
    if len(set(shingles)) / max(1, len(shingles)) < .87:
        return False, "CHUNK_REPETITIVE"
    old = tokens(previous)
    old12 = {tuple(old[i:i+12]) for i in range(0, max(0, len(old)-11), 3)}
    if old12 and sum(sh in old12 for sh in shingles) / max(1, len(shingles)) > .10:
        return False, "CHUNK_DUPLICATES_PRIOR"
    return True, "DRAFT_ONLY_NOT_SCIENTIFIC_QC"


def safe_json(path, maximum=200000):
    require(path.is_file() and not path.is_symlink(), "AUTHOR_INPUT_MISSING_OR_SYMLINK")
    require(0 < path.stat().st_size <= maximum, "AUTHOR_INPUT_SIZE")
    obj = json.loads(path.read_text(encoding="utf8"))
    require(isinstance(obj, dict), "AUTHOR_INPUT_NOT_OBJECT")
    return obj


def save_once(path, contents):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not path.is_symlink() and not path.exists(), "AUTHOR_IMMUTABLE_TARGET_EXISTS")
    fd, tmp = tempfile.mkstemp(prefix=".original-author-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        require(not path.exists() and not path.is_symlink(), "AUTHOR_RACE_TARGET")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def replace_status(path, row):
    require(not path.is_symlink(), "AUTHOR_UNSAFE_STATUS")
    raw = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf8")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".original-author-state-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def secret_key(path):
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value:
        return value
    if path.is_symlink() or not path.is_file():
        return ""
    st = path.stat()
    require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid()
            and not st.st_mode & 0o077 and st.st_size <= 512, "AUTHOR_API_KEY_FILE_PERMISSIONS")
    return path.read_text(encoding="ascii").strip()


def check_inputs(root, product):
    require(BOOK_ID.fullmatch(product) is not None, "AUTHOR_INVALID_PRODUCT")
    area = root / "production-instructions"
    require(area.is_dir() and not area.is_symlink(), "AUTHOR_FACTORY_AREA")
    bookdir = area / "stage-05/doctoral-monographs-100k-v1"
    plan = safe_json(bookdir / "plans" / (product + ".json"))
    require(plan.get("id") == product and plan.get("chapters_required") == CHAPTER_COUNT
            and plan.get("minimum_original_prose_words") == BOOK_MINIMUM
            and plan.get("commercial_release") is not True
            and plan.get("quality1000_approved") is False, "AUTHOR_UNVERIFIED_PLAN")
    chapters = plan.get("chapter_work_units")
    require(isinstance(chapters, list) and len(chapters) == CHAPTER_COUNT, "AUTHOR_CHAPTER_PLAN")
    evidence = safe_json(area / "stage-02/source-evidence" / (product + "--r001.json"), 1500000)
    require(evidence.get("schema") is not None, "AUTHOR_UNVERIFIED_SOURCE_EVIDENCE")
    return area, bookdir, plan, chapters, evidence


def existing_parts(bookdir, product):
    folder = bookdir / "authored-chunks" / product
    require(not folder.is_symlink(), "AUTHOR_UNSAFE_CHUNK_DIR")
    out = {i: [] for i in range(1, CHAPTER_COUNT + 1)}
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            require(not p.is_symlink(), "AUTHOR_UNSAFE_CHUNK_LINK")
            m = CHUNK_NAME.fullmatch(p.name)
            if not m:
                continue
            chapter = int(m.group(1))
            require(1 <= chapter <= CHAPTER_COUNT and p.is_file()
                    and p.stat().st_size <= 100000, "AUTHOR_BAD_CHUNK")
            out[chapter].append((p, p.read_text(encoding="utf8")))
    return out


def next_part(parts):
    for chapter in range(1, CHAPTER_COUNT + 1):
        words = sum(len(tokens(text)) for _, text in parts[chapter])
        if words < CHAPTER_TARGET:
            return chapter, len(parts[chapter]) + 1
    return None, None


def call_model(key, model, prompt, max_output_tokens, timeout=90):
    body = json.dumps({
        "model": model,
        "instructions": (
            "Act as a professional original textbook writer and rigorous educational editor. "
            "Write precise, substantive prose with practical examples and exercises. "
            "Do not invent measured outcomes, academic references, quotations, "
            "regulatory requirements or source access. Clearly distinguish worked "
            "hypothetical examples from scientific findings. "
            "No placeholder filler, repeated generic paragraphs, or fake peer review."
        ),
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "store": False
    }, ensure_ascii=False).encode("utf8")
    req = urllib.request.Request(MODEL_ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(3000000)
    except urllib.error.HTTPError as error:
        # HTTP response bodies may contain sensitive request echoes: never log.
        raise RuntimeError("AUTHOR_PROVIDER_HTTP_" + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("AUTHOR_PROVIDER_UNAVAILABLE") from None
    data = json.loads(raw.decode("utf8"))
    texts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            texts.extend(p.get("text", "") for p in item.get("content", [])
                         if p.get("type") == "output_text")
    result = "\n\n".join(x for x in texts if x.strip()).strip()
    usage = data.get("usage") or {}
    require(bool(result) and isinstance(usage.get("input_tokens"), int)
            and isinstance(usage.get("output_tokens"), int), "AUTHOR_PROVIDER_INCOMPLETE")
    return result, usage, str(data.get("id", ""))[:100]


def prepare_prompt(plan, unit, previous, evidence, chapter, part):
    # Stage2 is metadata/abstract research; no secret orders or private buyers
    # enter the external prompt. Do not pass entire source files.
    safe_evidence = {}
    for k in ("topic_id", "source_ids", "bibliography", "source_doi", "publisher_diversity", "sources", "claims"):
        if k in evidence:
            safe_evidence[k] = evidence[k]
    context = json.dumps(safe_evidence, ensure_ascii=False)[:3500]
    recent = previous[-1200:]
    return (
        "Write the NEXT original segment (aim 1400-2000 words) for a private "
        "advanced educational book. Do not repeat previous paragraphs. "
        "Return only the segment Markdown; no claims of approval or release.\n"
        "Book title: " + str(plan["selling_title"])[:260] + "\n"
        "Writing language: " + str(plan["selling_locale"])[:12] + "\n"
        "Chapter " + str(chapter) + " part " + str(part) + "\n"
        "Specific chapter assignment: " + str(unit.get("focus", unit.get("subject", "")))[:700] + "\n"
        "Indexed source metadata (not fulltext verified): " + context + "\n"
        "Last already-written context (do NOT duplicate): " + recent + "\n"
        "Write domain-specific analysis, actionable teaching methods, explicit "
        "scope limits, transparent hypothetical case studies with worked "
        "calculations, exercises and answers; explain what primary evidence "
        "still needs professional verification. Never invent DOI or factual outcomes."
    )


def assemble_if_complete(bookdir, plan, parts):
    if any(sum(len(tokens(t)) for _, t in parts[i]) < CHAPTER_TARGET
           for i in range(1, CHAPTER_COUNT + 1)):
        return False
    body = "# " + plan["selling_title"] + "\n\n"
    for i in range(1, CHAPTER_COUNT + 1):
        body += "\n\n## Chapter " + str(i) + "\n\n"
        body += "\n\n".join(x for _, x in parts[i]) + "\n"
    all_words = len(tokens(body))
    require(all_words >= BOOK_MINIMUM, "AUTHOR_ASSEMBLY_INSUFFICIENT_WORDS")
    words = tokens(body)
    shingles = [tuple(words[i:i+12]) for i in range(0, len(words)-11, 6)]
    require(len(set(shingles)) / max(1, len(shingles)) >= .87,
            "AUTHOR_ASSEMBLY_REPETITIVE")
    require(len(set(words)) >= 1000, "AUTHOR_ASSEMBLY_LEXICAL_PADDING")
    output = bookdir / "authored-books" / (plan["id"] + ".md")
    require(not output.exists() and not output.is_symlink(), "AUTHOR_COMPLETED_BOOK_EXISTS")
    save_once(output, body.encode("utf8"))
    report = {"schema": SCHEMA, "product_id": plan["id"],
              "original_prose_words_unreviewed": all_words,
              "complete_length_only": True, "subject_matter_verified": False,
              "independent_science_review": False, "qc1000_approved": False,
              "commercial_release": False,
              "sha256": hashlib.sha256(body.encode("utf8")).hexdigest()}
    save_once(bookdir / "authored-books" / (plan["id"] + ".json"),
              (json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n").encode("utf8"))
    return True


def run(args):
    root = Path(args.factory_private).resolve()
    area, bookdir, plan, chapters, evidence = check_inputs(root, args.product)
    folder = bookdir / "authored-chunks" / args.product
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not folder.is_symlink(), "AUTHOR_UNSAFE_TARGET_DIR")
    lock = folder / ".authoring.lock"
    require(not lock.is_symlink(), "AUTHOR_UNSAFE_LOCK")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        parts = existing_parts(bookdir, args.product)
        chapter, part = next_part(parts)
        if chapter is not None:
            attempted = re.compile(r"chapter-%02d-part-([0-9]{3})\.md(?:\.rejected)?\Z" % chapter)
            previous_ids = [int(m.group(1)) for child in folder.iterdir()
                            if child.is_file() and not child.is_symlink()
                            for m in [attempted.fullmatch(child.name)] if m]
            part = max(previous_ids, default=0) + 1
            require(part <= 999, "AUTHOR_PART_LIMIT")
        n = sum(len(tokens(text)) for group in parts.values() for _, text in group)
        key_path = Path(args.api_key_file)
        api_ready = bool(secret_key(key_path))
        preflight = {"schema": SCHEMA, "product": args.product,
                     "draft_words_so_far": n, "chapter_next": chapter,
                     "part_next": part, "api_credential_available": api_ready,
                     "local_inference_not_required": True,
                     "independent_qc1000_passed": False,
                     "published": False, "can_charge": False}
        if not args.execute or chapter is None:
            preflight["state"] = "DRAFT_COMPLETE_AWAITING_QC" if chapter is None else "PREFLIGHT_ONLY_NO_CHARGE"
            return preflight
        require(api_ready, "AUTHOR_API_CREDENTIAL_UNAVAILABLE")
        require(0 < args.max_total_usd <= 1000 and
                0 < args.input_usd_per_million < 100 and
                0 < args.output_usd_per_million < 100 and
                1000 <= args.max_output_tokens <= 8000,
                "AUTHOR_BUDGET_OR_PRICE_NOT_APPROVED")
        ledger_path = folder / "paid-attempt-ledger.json"
        ledger = safe_json(ledger_path) if ledger_path.exists() else {
            "schema": SCHEMA, "product": args.product, "reserved_usd": 0, "attempts": []}
        require(ledger.get("schema") == SCHEMA and ledger.get("product") == args.product
                and isinstance(ledger.get("reserved_usd"), (int, float))
                and isinstance(ledger.get("attempts"), list), "AUTHOR_LEDGER_INVALID")
        previous = "\n\n".join(t for _, t in parts[chapter])
        prompt = prepare_prompt(plan, chapters[chapter - 1], previous, evidence, chapter, part)
        # UTF-8 bytes are a conservative upper bound for practical BPE input tokens.
        reservation = round(
            (len(prompt.encode("utf8")) * args.input_usd_per_million +
             args.max_output_tokens * args.output_usd_per_million) / 1000000, 6)
        require(ledger["reserved_usd"] + reservation <= args.max_total_usd,
                "AUTHOR_OWNER_BUDGET_EXHAUSTED")
        attempt = {"chapter": chapter, "part": part, "model": args.model,
                   "reserved_usd": reservation, "state": "RESERVED_BEFORE_NETWORK",
                   "utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        ledger["attempts"].append(attempt)
        ledger["reserved_usd"] = round(ledger["reserved_usd"] + reservation, 6)
        replace_status(ledger_path, ledger)
        # One real external model request only; no retries or automatic invoice exposure.
        output, usage, response_id = call_model(
            secret_key(key_path), args.model, prompt, args.max_output_tokens)
        accepted, reason = distinct_enough(output, previous)
        name = "chapter-%02d-part-%03d.md" % (chapter, part)
        path = folder / name
        if accepted:
            save_once(path, output.encode("utf8"))
        else:
            save_once(folder / (name + ".rejected"), output.encode("utf8"))
        attempt.update({"state": "DRAFT_ACCEPTED" if accepted else "DRAFT_REJECTED",
                        "reason": reason, "provider_response_id": response_id,
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                        "prose_words": len(tokens(output)),
                        "content_sha256": hashlib.sha256(output.encode("utf8")).hexdigest()})
        replace_status(ledger_path, ledger)
        if accepted:
            parts[chapter].append((path, output))
            assembled = assemble_if_complete(bookdir, plan, parts)
        else:
            assembled = False
        return {"schema": SCHEMA, "product": args.product, "chapter": chapter,
                "part": part, "real_model_response_received": True,
                "original_draft_chunk_accepted": accepted, "chunk_words": len(tokens(output)),
                "total_draft_prose_words": n + (len(tokens(output)) if accepted else 0),
                "private_book_assembled": assembled,
                "independent_qc1000_passed": False, "published": False,
                "owner_budget_reserved_usd": ledger["reserved_usd"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--product", default="AGRI-001")
    p.add_argument("--api-key-file",
                   default="/home/githubops/factory-runtime/operations/production-instructions/.openai-authoring-api-key")
    p.add_argument("--model", default="gpt-5-mini")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--max-total-usd", type=float, default=0)
    p.add_argument("--input-usd-per-million", type=float, default=0)
    p.add_argument("--output-usd-per-million", type=float, default=0)
    p.add_argument("--max-output-tokens", type=int, default=5000)
    a = p.parse_args()
    try:
        print(json.dumps(run(a), ensure_ascii=False, sort_keys=True), flush=True)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        print("FACTORY_AUTHOR_BLOCKED:" + type(error).__name__ + ":" +
              str(error)[:160], file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()

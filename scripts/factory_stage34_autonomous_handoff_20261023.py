#!/usr/bin/env python3
"""Evidence-preserving private stages 3 (design) and 4 (prototype).

Stage 2's validated, hash-linked research is the ONLY eligible input. This
worker creates actual bilingual editorial designs and small exercise prototypes;
it does not create a full scientific manuscript, assert expert review, touch
websites, or grant commercial/quality approval. Stage 5 remains responsible for
full authorship and production. Durable receipts survive restarts.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

HANDOFF = "saeit.factory.stage-handoff.v1"
RESEARCH = "saeit.factory.stage2-desk-research.v1"
DESIGN = "saeit.factory.stage3-bilingual-design.v1"
PROTOTYPE = "saeit.factory.stage4-learning-prototype.v1"
NAME = re.compile(r"WO-[0-9]+--r([0-9]+)\.json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
LOCALES = ("fa-IR", "en-US")
MAX_BYTES = 1_000_000

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()

def private_dir(path):
    if path.is_symlink():
        raise RuntimeError("STAGE34_UNSAFE_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("STAGE34_UNSAFE_DIRECTORY")
    os.chmod(path, 0o700)

def read(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("STAGE34_FILE_NOT_REGULAR:" + path.name)
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise RuntimeError("STAGE34_FILE_SIZE_INVALID:" + path.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("STAGE34_JSON_OBJECT_REQUIRED")
    return value

def atomic(path, value):
    private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".stage34-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, sort_keys=True, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def once(path, value):
    if path.exists() or path.is_symlink():
        if read(path) != value:
            raise RuntimeError("STAGE34_IMMUTABLE_OUTPUT_CONFLICT:" + path.name)
        return False
    atomic(path, value)
    return True

def deny_approval(value):
    for key in ("quality1000_approved", "commercial_release", "public_distribution_allowed"):
        if value.get(key) is not False:
            raise RuntimeError("STAGE34_RELEASE_GUARD_INVALID:" + key)

def verified_stage2(area, name):
    if NAME.fullmatch(name) is None:
        raise RuntimeError("STAGE34_INVALID_ORDER_NAME")
    inbox = read(area / "stage-03" / "inbox" / name)
    research = read(area / "stage-02" / "completed-dossiers" / name)
    receipt = read(area / "stage-02" / "receipts" / name)
    if (inbox.get("schema") != HANDOFF or inbox.get("previous_stage") != 2
            or inbox.get("next_stage") != 3
            or inbox.get("desk_research_file") != name
            or not isinstance(inbox.get("order_id"), str)
            or not name.startswith(inbox["order_id"] + "--")
            or type(inbox.get("revision")) is not int
            or inbox["revision"] != int(NAME.fullmatch(name).group(1))
            or inbox.get("desk_research_sha256") != digest(research)
            or research.get("schema") != RESEARCH
            or research.get("order_id") != inbox["order_id"]
            or research.get("revision") != inbox["revision"]
            or research.get("stage2_documentation_complete") is not True
            or research.get("independent_scientific_review") is not False
            or research.get("manuscript_created") is not False
            or receipt.get("schema") != HANDOFF
            or receipt.get("stage_2_completed") is not True
            or receipt.get("research_sha256") != digest(research)
            or receipt.get("stage_3_packet_sha256") != digest(inbox)
            or receipt.get("order_id") != inbox["order_id"]):
        raise RuntimeError("STAGE34_STAGE2_CHAIN_INTEGRITY_FAILED")
    deny_approval(inbox)
    deny_approval(research)
    sources = research.get("sources")
    claims = research.get("claims")
    scopes = research.get("locale_scopes")
    if (not isinstance(sources, list) or len(sources) < 4
            or not isinstance(claims, list) or len(claims) < 5
            or not isinstance(scopes, dict) or set(scopes) != set(LOCALES)):
        raise RuntimeError("STAGE34_INSUFFICIENT_RESEARCH")
    ids = {s.get("id") for s in sources if isinstance(s, dict)}
    if len(ids) != len(sources) or None in ids:
        raise RuntimeError("STAGE34_DUPLICATE_OR_INVALID_SOURCES")
    seen = set()
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get("id"), str)
                or claim["id"] in seen
                or not isinstance(claim.get("statement"), str)
                or len(claim["statement"].strip()) < 35
                or not isinstance(claim.get("source_ids"), list)
                or not claim["source_ids"]
                or not set(claim["source_ids"]).issubset(ids)):
            raise RuntimeError("STAGE34_SOURCE_CLAIM_LINK_INVALID")
        seen.add(claim["id"])
    # The original input order is required for scoped product identity. Do not
    # invent an unrelated item or infer a saleable product from papers.
    first = area / "stage-02" / "inbox" / name
    if not first.is_file():
        raise RuntimeError("STAGE34_STAGE1_ORIGINAL_REQUIRED")
    origin = read(first)
    if (origin.get("schema") != HANDOFF
            or origin.get("order_id") != inbox["order_id"]
            or origin.get("revision") != inbox["revision"]
            or research.get("stage_1_handoff_sha256") != digest(origin)):
        raise RuntimeError("STAGE34_ORIGIN_HASH_MISMATCH")
    order = origin.get("work_order")
    if not isinstance(order, dict) or order.get("id") != inbox["order_id"]:
        raise RuntimeError("STAGE34_ORIGINAL_WORKORDER_INVALID")
    editions = order.get("editions")
    if not isinstance(editions, list):
        raise RuntimeError("STAGE34_NO_EDITIONS")
    translated = {x.get("locale"): x for x in editions if isinstance(x, dict)}
    if set(translated) != set(LOCALES):
        raise RuntimeError("STAGE34_MISSING_BILINGUAL_EDITIONS")
    return inbox, research, order, translated

def make_design(inbox, research, order, editions):
    chapters = []
    prompts = (
        ("شناخت موضوع و تعریف اصطلاحات", "Topic and terminology"),
        ("بررسی شواهد و محدودیت‌ها", "Evidence and limitations"),
        ("طراحی مشاهده و ثبت داده", "Observation and data recording"),
        ("مقایسه روش‌ها و تصمیم‌گیری", "Comparing approaches and decisions"),
        ("ارزیابی خطا و ایمنی", "Error analysis and safety"),
    )
    for n, claim in enumerate(research["claims"][:12], 1):
        fa, en = prompts[(n - 1) % len(prompts)]
        chapters.append({
            "unit": n, "title_fa": f"{fa} — بخش {n}",
            "title_en": f"{en} — unit {n}",
            "source_claim_id": claim["id"],
            "source_ids": claim["source_ids"],
            "research_statement_for_verification_only": claim["statement"],
            "learning_task_fa": "با مراجعه به منبع، ادعا و محدودیت کاربرد آن را بررسی و با واحدهای بومی ثبت کنید.",
            "learning_task_en": "Check the referenced claim and its limitations; record locally applicable units and conditions.",
            "required_output": "original_explanation_plus_example_and_answer_key",
            "scientific_validation_pending": True
        })
    return {
        "schema": DESIGN, "stage": 3, "order_id": inbox["order_id"],
        "revision": inbox["revision"], "source_product_id": research["source_product_id"],
        "stage2_research_sha256": digest(research),
        "design_status": "bilingual_evidence_mapped_curriculum_blueprint",
        "edition_plans": {loc: {
            "title": editions[loc].get("title"),
            "audience": editions[loc].get("audience"),
            "research_scope": research["locale_scopes"][loc],
            "chapters_requested": len(chapters),
            "units_localized": True
        } for loc in LOCALES},
        "chapters": chapters,
        "authoring_acceptance": [
            "Write original, complete Persian and English explanations for each unit.",
            "Verify every scientific statement against the original full source.",
            "Provide worked examples, exercises, answer key, and editable activity sheets.",
            "Review locale-specific climate, units, regulatory and safety context.",
            "Independently check technical and scientific accuracy before release."
        ],
        "full_manuscript_created": False, "scientific_review_completed": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }

def stage3(area, name):
    inbox, research, order, editions = verified_stage2(area, name)
    design = make_design(inbox, research, order, editions)
    created = once(area / "stage-03" / "completed-designs" / name, design)
    move = {
        "schema": HANDOFF, "order_id": inbox["order_id"],
        "revision": inbox["revision"], "previous_stage": 3, "next_stage": 4,
        "stage3_design_sha256": digest(design),
        "stage2_research_sha256": digest(research),
        "stage_4_status": "received_pending_original_learning_prototype",
        "full_manuscript_created": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False
    }
    once(area / "stage-04" / "inbox" / name, move)
    proof = {
        "schema": HANDOFF, "order_id": inbox["order_id"],
        "revision": inbox["revision"], "stage_3_design_completed": True,
        "stage_4_inbox_file": name, "design_sha256": digest(design),
        "stage_4_packet_sha256": digest(move),
        "scientific_review_completed": False, "quality1000_approved": False
    }
    once(area / "stage-03" / "receipts" / name, proof)
    return created

def stage4(area, name):
    if NAME.fullmatch(name) is None:
        raise RuntimeError("STAGE34_INVALID_STAGE4_NAME")
    handoff = read(area / "stage-04" / "inbox" / name)
    design = read(area / "stage-03" / "completed-designs" / name)
    proof = read(area / "stage-03" / "receipts" / name)
    _, research, _, _ = verified_stage2(area, name)
    if (handoff.get("schema") != HANDOFF
            or handoff.get("previous_stage") != 3 or handoff.get("next_stage") != 4
            or handoff.get("order_id") != design.get("order_id")
            or handoff.get("revision") != design.get("revision")
            or handoff.get("stage3_design_sha256") != digest(design)
            or handoff.get("stage2_research_sha256") != digest(research)
            or design.get("schema") != DESIGN
            or design.get("stage2_research_sha256") != digest(research)
            or proof.get("schema") != HANDOFF
            or proof.get("stage_3_design_completed") is not True
            or proof.get("design_sha256") != digest(design)
            or proof.get("stage_4_packet_sha256") != digest(handoff)):
        raise RuntimeError("STAGE34_STAGE3_CHAIN_INTEGRITY_FAILED")
    deny_approval(handoff)
    deny_approval(design)
    activities = []
    for unit in design["chapters"][:5]:
        activities.append({
            "unit": unit["unit"],
            "traceable_claim_id": unit["source_claim_id"],
            "traceable_source_ids": unit["source_ids"],
            "prototype_fa": "کاربرگ آزمایشی: منبع را بخوانید؛ ادعا، شرایط کاربرد، محدودیت و یک پرسش قابل‌آزمون را ثبت کنید.",
            "prototype_en": "Pilot worksheet: read the cited source; log its claim, application conditions, limitations, and one testable question.",
            "data_fields": ["reference", "observed_condition", "measurement_unit",
                            "claim_limitations", "testable_question", "reviewer_notes"],
            "requires_original_content_authoring": True
        })
    prototype = {
        "schema": PROTOTYPE, "stage": 4, "order_id": handoff["order_id"],
        "revision": handoff["revision"],
        "stage3_design_sha256": digest(design),
        "source_bibliography": [{
            "id": s["id"], "title": s["title"], "url": s["url"],
            "publisher": s["publisher"]} for s in research["sources"]],
        "edition_titles": {loc: design["edition_plans"][loc]["title"] for loc in LOCALES},
        "bilingual_sample_activities": activities,
        "status": "source_linked_preproduction_worksheet_prototype",
        "limitations": "A private traceable learning-activity sample only; not a manuscript or independently tested agricultural recommendation.",
        "full_manuscript_created": False,
        "independent_scientific_review": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False
    }
    created = once(area / "stage-04" / "completed-prototypes" / name, prototype)
    move = {
        "schema": HANDOFF, "order_id": handoff["order_id"],
        "revision": handoff["revision"], "previous_stage": 4, "next_stage": 5,
        "stage4_prototype_sha256": digest(prototype),
        "stage3_design_sha256": digest(design),
        "stage_5_status": "received_pending_full_original_manuscript_production",
        "full_manuscript_created": False, "quality1000_approved": False,
        "commercial_release": False, "public_distribution_allowed": False
    }
    once(area / "stage-05" / "inbox" / name, move)
    proof4 = {
        "schema": HANDOFF, "order_id": handoff["order_id"],
        "revision": handoff["revision"], "stage_4_prototype_completed": True,
        "stage_5_inbox_file": name, "prototype_sha256": digest(prototype),
        "stage_5_packet_sha256": digest(move),
        "scientific_review_completed": False, "quality1000_approved": False
    }
    once(area / "stage-04" / "receipts" / name, proof4)
    return created

def fair_batch(area, stage, names, batch):
    """Cycle independently through stage 3/4 inboxes across cron invocations."""
    if stage not in (3, 4):
        raise RuntimeError("STAGE34_INVALID_SCHEDULER_STAGE")
    path = area / ("stage-%02d" % stage) / "round-robin-cursor.json"
    if path.is_symlink():
        raise RuntimeError("STAGE34_CURSOR_SYMLINK")
    schema = "saeit.factory.stage%d.round-robin.v1" % stage
    state = read(path) if path.exists() else {"schema": schema, "next_index": 0}
    if (state.get("schema") != schema or type(state.get("next_index")) is not int
            or state["next_index"] < 0):
        raise RuntimeError("STAGE34_CURSOR_INVALID")
    total = len(names)
    first = state["next_index"] % total if total else 0
    count = min(batch, total)
    selected = [names[(first + i) % total] for i in range(count)]
    after = {"schema": schema,
             "next_index": (first + count) % total if total else 0}
    return selected, path, after


def execute(root, batch=250):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError("STAGE34_PRIVATE_FACTORY_MISSING")
    area = root / "production-instructions"
    for n in (3, 4, 5):
        private_dir(area / ("stage-%02d" % n) / "inbox")
    lock = area / ".stage34-worker.lock"
    if lock.is_symlink():
        raise RuntimeError("STAGE34_LOCK_SYMLINK")
    with lock.open("a+b") as guard:
        os.chmod(lock, 0o600)
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        totals = {}
        for n, fn in ((3, stage3), (4, stage4)):
            inbox = area / ("stage-%02d" % n) / "inbox"
            names = sorted(p.name for p in inbox.iterdir()
                           if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
            selected, cursor_path, next_state = fair_batch(area, n, names, batch)
            fresh, invalid = 0, 0
            for name in selected:
                try:
                    fresh += int(fn(area, name))
                except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
                    invalid += 1
                    atomic(area / ("stage-%02d" % n) / "blocked" / name, {
                        "order_file": name, "stage": n,
                        "status": "requires_own_stage_rework",
                        "reason": type(exc).__name__ + ":" + str(exc)[:200],
                        "promoted": False
                    })
            atomic(cursor_path, next_state)
            totals["stage%d_new" % n] = fresh
            totals["stage%d_blocked_this_tick" % n] = invalid
            totals["stage%d_inbox_total" % n] = len(names)
            totals["stage%d_completed_total" % n] = len(list(
                (area / ("stage-%02d" % n) / "receipts").glob("WO-*.json")))
        totals["stage5_inbox_total"] = len(list(
            (area / "stage-05" / "inbox").glob("WO-*.json")))
        totals["websites_modified"] = False
        totals["independent_scientific_reviews_created"] = 0
        totals["full_manuscripts_claimed"] = 0
        totals["public_releases"] = 0
        atomic(area / "stage-04" / "autonomous-status.json", totals)
        return totals

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--batch", type=int, default=250)
    args = p.parse_args()
    if not 1 <= args.batch <= 1000:
        raise RuntimeError("STAGE34_INVALID_BATCH")
    report = execute(args.factory_private, args.batch)
    for key, value in sorted(report.items()):
        print("FACTORY_STAGE34_" + key.upper() + "=" + str(value).lower()
              if isinstance(value, bool) else
              "FACTORY_STAGE34_" + key.upper() + "=" + str(value))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FACTORY_STAGE34_ERROR=" + type(exc).__name__ + ":" + str(exc)[:200],
              file=sys.stderr)
        raise SystemExit(1)

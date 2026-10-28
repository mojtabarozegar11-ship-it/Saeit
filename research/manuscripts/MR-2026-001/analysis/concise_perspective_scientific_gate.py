#!/usr/bin/env python3
"""Mechanical author-review QA for concise MR-2026-001 Perspective.

NOT a scientific originality decision, independent human review, or permission
to submit. Tests the actual author-review text and preserves reproducible JSON.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "MR-2026-001_CONCISE_PERSPECTIVE_AUTHOR_SCIENTIFIC_REVIEW_2026-10-25.md"
OUT = ROOT / "MR-2026-001_CONCISE_PERSPECTIVE_MECHANICAL_QA_2026-10-25.json"

def run():
    s = MANUSCRIPT.read_text(encoding="utf-8")
    abstract = s.split("## Abstract", 1)[1].split("## 1.", 1)[0]
    body = s.split("## References", 1)[0]
    refs = s.split("## References", 1)[1]
    citations = sorted(set(int(i) for group in re.findall(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", body)
                           for i in re.findall(r"\d+", group)))
    # Expand explicit inclusive citation ranges (e.g., [4–7]).
    for a,b in re.findall(r"\[(\d+)\s*[–-]\s*(\d+)\]",body):
        citations = sorted(set(citations)|set(range(int(a),int(b)+1)))
    ref_ids = [int(x) for x in re.findall(r"(?m)^(\d+)\. [^\n]+https://doi\.org/10\.", refs)]
    abstract_words = len(abstract.split())
    total_words = len(body.split())
    checks = {
        "abstract_under_250":abstract_words < 250,
        "concise_perspective_1500_to_5000_words_internal_not_publisher_rule":1500<=total_words<=5000,
        "all_12_references_present_in_order":ref_ids==list(range(1,13)),
        "all_12_references_cited":set(citations)==set(range(1,13)),
        "no_unresolved_author_placeholders_in_manuscript":not any(
            x in body for x in ("[AUTHOR", "[AFFILIATION", "AUTHOR TO VERIFY", "FUNDING UNKNOWN")),
        "car_duration_not_adherence":"45/72" in body and "engagement" in body.lower(),
        "car_unverified_table_cells_excluded":"exclude those disputed category counts" in body,
        "amini_F7_source_conflict_retained":"−1.4 kg/m³" in body and "292.7 mm" in body,
        "cvejic_83_percent_not_misread_as_metered_savings":"83%" in body and "simulated" in body.lower(),
        "no_pooled_prevalence_or_causal_claim":"not a comprehensive evidence search" in body and "No study-level inclusion probabilities" in body,
        "method_is_proposal_not_validated":"not a validated scale" in body,
        "prior_art_acknowledged":"not a newly discovered adoption problem" in body.lower(),
    }
    out = {
        "source_path":str(MANUSCRIPT.relative_to(ROOT)),
        "run_utc":datetime.now(timezone.utc).isoformat(),
        "abstract_words":abstract_words,
        "body_words_excluding_reference_list":total_words,
        "reference_ids":ref_ids,
        "in_text_citations":citations,
        "mechanical_checks":checks,
        "mechanical_pass":all(checks.values()),
        "external_full_texts_all_verified":False,
        "new_theory_or_instrument_validated":False,
        "independent_human_peer_review_completed":False,
        "scientific_novelty_cleared":False,
        "human_author_material_contribution_confirmed":False,
        "author_final_approval_confirmed":False,
        "submission_allowed":False,
        "decision":"AUTHOR SCIENTIFIC REVIEW CANDIDATE; NOT SUBMISSION-READY",
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if not out["mechanical_pass"]:
        raise SystemExit("MECHANICAL GATE FAILED; no approval inferred")
if __name__=="__main__":
    run()

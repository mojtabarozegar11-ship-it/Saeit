#!/usr/bin/env python3
"""Conservative, source-aware mechanical pre-submission gate for MR-2026-001.

Does NOT substitute for independent human peer review, source-page inspection,
authorship, scientific novelty assessment or publisher approval. CI success
means mechanical/provenance checks passed, NOT a journal-ready manuscript.
"""
import json
import re
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
CAND=BASE/"MR-2026-001_DISCOVER_AGRICULTURE_PERSPECTIVE_AUTHOR_REVIEW_CANDIDATE_2026-10-25.md"
REVIEW=BASE/"C19_CLEAN_EIGHT_CASE_CRITICAL_NARRATIVE_MANUSCRIPT_2026-10-25.md"
LOG=BASE/"C23_TRACEABLE_NON_SYSTEMATIC_DISCOVERY_AND_PRIOR_ART_LOG_2026-10-25.md"
ADVERSARIAL=BASE/"C22_AI_INTERNAL_SANRA_SIX_ITEM_ADVERSARIAL_DECISION_2026-10-25.md"
OUT=BASE/"MR-2026-001_MECHANICAL_QA_NOT_SCIENTIFIC_CLEARANCE_2026-10-25.json"

def count_words(s):
    s=re.sub(r"[*_#]","",s)
    return len(s.strip().split())

def run():
    a=CAND.read_text(encoding="utf-8")
    b=REVIEW.read_text(encoding="utf-8")
    log=LOG.read_text(encoding="utf-8")
    decision=ADVERSARIAL.read_text(encoding="utf-8")
    abstract=a.split("## Abstract",1)[1].split("## 1. Introduction",1)[0].strip()
    reference_section=a.split("## References",1)[1].split("## Declarations",1)[0]
    numbered=re.findall(r"(?m)^([0-9]+)\. (.+)$",reference_section)
    dois=re.findall(r"https://doi\.org/(10\.[^\s)]+)",reference_section)
    checks={
      "publisher_abstract_under_250_words":count_words(abstract)<250,
      "exactly_16_sequential_numbered_references":[int(n) for n,_ in numbered]==list(range(1,17)),
      "sixteen_unique_reference_dois":len(dois)==16 and len(set(dois))==16,
      "both_manuscripts_explicitly_avoid_car_disputed_counts":all(
         "disputed" in text.lower() and "excluded" in text.lower() and
         "45" in text and "13" in text and "14" in text for text in (a,b)),
      "both_manuscripts_acknowledge_source_denominator_limits":all(
         "Amini" in text and "Cveji" in text and "F7" in text and "83%" in text for text in (a,b)),
      "both_manuscripts_include_measured_observed_self_report_model_unverified":all(
         "physical" in text.lower() and "self-report" in text.lower() and
         "model" in text.lower() and "unverified" in text.lower() for text in (a,b)),
      "both_manuscripts_acknowledge_IWMI_81_tools_and_same_journal_prior_art":all(
         "81" in text and "Mabhaudhi" in text and "Ofosu-Ampong" in text for text in (a,b)),
      "supplementary_search_log_explicitly_non_systematic":"not a retroactively reconstructed log" in log.lower() and
         "not a systematic" in log.lower(),
      "source_arithmetic_74_vs_72_retained_as_uncertainty":"26+7+3+6+15+17=74" in decision and
         "45+13+14=72" in log and all(str(x) in decision for x in (45,13,14,72)),
      "no_unqualified_first_ever_or_guaranteed_publication":(not re.search(r"\b(guaranteed acceptance|ready for immediate submission)\b",a,re.I) and all(re.search(r"\b(not|no)\s+(?:a\s+)?$",a[max(0,m.start()-30):m.start()],re.I) for m in re.finditer(r"\bfirst[- ]ever\b",a,re.I))),
      "journal_author_fields_explicitly_unverified":"[AUTHOR" in a and
         "NOT" in decision and "MAJOR REVISION" in decision,
    }
    blockers={
       "full_text_restricted_sources":True,
       "historical_eight_case_search_selection_not_fully_reconstructible":True,
       "Car_original_typeset_Table_5_not_visually_checked":True,
       "Amini_F7_and_Cvejic_83_percent_require_uncertainty":True,
       "novelty_not_independently_validated_against_prior_art":True,
       "human_author_substantive_contribution_and_final_approval":True,
       "truthful_affiliation_funding_COI_AI_and_permissions":True,
       "journal_specific_final_approval_and_fees":True,
    }
    result={
       "source":"MR-2026-001 research branch, canonical source-locked texts",
       "abstract_words":count_words(abstract),
       "candidate_words":count_words(a),
       "review_words":count_words(b),
       "numbered_references":len(numbered),
       "unique_dois":len(set(dois)),
       "mechanical_checks":checks,
       "mechanical_pass":all(checks.values()),
       "unresolved_scientific_and_author_blockers":blockers,
       "scientifically_cleared":False,
       "author_approved":False,
       "publisher_submitted":False,
       "journal_manuscript_id":None,
       "interpretation":"Only mechanical, bibliographic and conservative provenance checks; NOT peer review or a publishability score."
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["mechanical_pass"]:
        raise SystemExit("FAIL: mechanical/provenance manuscript gate")
if __name__=="__main__":
    run()

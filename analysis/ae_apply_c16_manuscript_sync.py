#!/usr/bin/env python3
"""Apply the independently documented C16 scientific addendum to AE manuscript.

Idempotent, fail-closed; GitHub Actions commits on the research branch only.
"""
from pathlib import Path

p = Path("research/manuscripts/AE-2026-001/AE-2026-001_FIRST_FULL_EMPIRICAL_MANUSCRIPT_DRAFT_2026-10-25.md")
c16 = Path("research/manuscripts/AE-2026-001/AE-2026-001_C16_REGION_STANDARDIZED_COHORT_MEAN_DECOMPOSITION_2026-10-26.md")
if not p.is_file() or not c16.is_file():
    raise SystemExit("Missing source manuscript or C16 evidence; no change")
text = p.read_text(encoding="utf-8")
if "### 2.11 Exploratory regional decomposition" in text and "### 3.21 Regional composition" in text:
    print("Already applied C16, no change")
    raise SystemExit(0)
if "### 2.11" in text or "### 3.21" in text:
    raise SystemExit("Conflicting subsection numbering; no change")
for heading in ("## 3. Results", "## 4. Discussion"):
    if text.count(heading) != 1:
        raise SystemExit(f"Missing/duplicate heading {heading}; no change")
methods = """### 2.11 Exploratory regional decomposition of the 2019–2023 cohort mean (post hoc)

We decomposed the equal-economy mean growth difference between the 153-economy three-endpoint cohort and the 169-economy 2019/2023 cohort into changes in regional sample shares and changes in observed within-region country means. With baseline/pooled regional shares w_B,r and w_P,r and regional means m_B,r and m_P,r, the exact identity is: mean_P − mean_B = Σ_r[(w_P,r − w_B,r)m_B,r] + Σ_r[w_P,r(m_P,r − m_B,r)]. The baseline-reference decomposition is descriptive, not unique or causal. It was computed from the same source-hashed 217-economy WDI panel and seven official region labels; excluding CAF and DJI is a **post-hoc influence check only**. Full country source, code, formulas and region table are documented in [C16](AE-2026-001_C16_REGION_STANDARDIZED_COHORT_MEAN_DECOMPOSITION_2026-10-26.md). This is not a historical-vintage, representative-population or methodological-novelty claim.

"""
results = """### 3.21 Regional composition and within-region contributions to the 2019–2023 mean gap (post hoc)

The equal-economy mean annual log growth was **+0.541735** in the 153-economy baseline and **+0.810142** in the 169-economy eligible cohort, a gap of **+0.268407 log-percentage points/year**. The exact baseline-region identity decomposed the gap into **−0.044876** due to regional sample-share reweighting and **+0.313283** due to within-region sample-mean replacement. The largest positive within-region contributions were **+0.184244** for the Middle East/North Africa/Afghanistan/Pakistan region and **+0.179274** for Sub-Saharan Africa; East Asia/Pacific contributed **−0.098244**. In a strictly post-hoc diagnostic excluding CAF and DJI from the pooled group only, the mean gap fell to **+0.006171** (composition **−0.032963**, within-region **+0.039134**). These are algebraic components of **sample selection**, not region effects, causal drivers, WDI vintage revisions, a new estimator or a rationale to discard influential observations. The full reproducible seven-region decomposition appears in [C16](AE-2026-001_C16_REGION_STANDARDIZED_COHORT_MEAN_DECOMPOSITION_2026-10-26.md).

"""
text = text.replace("## 3. Results", methods + "## 3. Results")
text = text.replace("## 4. Discussion", results + "## 4. Discussion")
if not ("### 2.11" in text and "### 3.21" in text):
    raise SystemExit("Insertion verification failed; no change")
p.write_text(text, encoding="utf-8")
print(f"Inserted C16 Methods and Results into {p}; characters={len(text)}")

# MR-2026-001 C46 — Amini F7: partial resolution of 1.3 vs 1.4 by source-table arithmetic

**Date:** 27 October 2026. **Source:** Amini, Emami and Dehghanisanij, *Scientific Reports* 15:42480 (2025), DOI https://doi.org/10.1038/s41598-025-26567-z ; original publisher's open HTML, Tables 4–5, "Water productivity and crop yield" and Conclusion, independently re-inspected today. This is a **secondary arithmetic audit**, not new field data or an erratum.

## Exact F7 primary-source inputs (apple, basin irrigation)
From the publisher's Table 4:
- Treatment gross irrigation depth **1057.6 mm**, control **764.9 mm**.
- Treatment crop yield **48.9 tonnes/ha**, control **45.6 tonnes/ha**.
- Table 4 *displayed rounded* water productivity **4.6** treatment versus **6.0 kg/m³** control.

Unit conversion for a depth-based gross-water-productivity measure: 1 t/ha divided by 1 mm = 100 kg/m³. Therefore calculate WP = 100 × yield(t/ha)/gross irrigation depth(mm), **only if the source uses that denominator**.

- Treatment WP = 100 × 48.9/1057.6 = **4.623676 kg/m³**.
- Control WP = 100 × 45.6/764.9 = **5.961564 kg/m³**.
- Difference (treatment − control) = **−1.337887 kg/m³**, which rounds to **−1.3 kg/m³** at one decimal.
- Subtracting the *displayed one-decimal WP cells* gives 4.6 − 6.0 = **−1.4 kg/m³**.
- Relative difference from the unrounded ratios = **−22.442%**.
- Gross-depth increase = 1057.6 − 764.9 = **292.7 mm**, matching the article's text; relative increase **38.266%**.
- Yield difference = 48.9 − 45.6 = **3.3 t/ha** from the displayed Table 4 values, whereas the adjacent paragraph says **3.4 t/ha**. This could reflect unreported underlying precision or a separate text discrepancy; the displayed values alone cannot decide.

## What is now resolved and what remains open
The published **−1.3 kg/m³** F7 narrative and **−1.4 kg/m³** later narrative **can be reconciled by rounding order**: computing WP from source yields and depths before rounding gives −1.3, while subtracting already rounded Table 4 WP cells gives −1.4. These two sentences need not indicate different field measurements.

**Still unresolved:** the publisher's Conclusion describes an F7 WP decrease of **0.1 kg/m³**; neither calculation above yields this value. The publisher's Table 5 column labeled **"Increase in water productivity (%)"** lists **−3.22** for F7; it matches neither the recomputed absolute change (−1.337887 kg/m³) nor the relative change (−22.442%) under the displayed Table 4 inputs. A separate, unstated denominator or table error is possible; no correction is asserted. The source's Table 5 also contains other figures that do not trivially reproduce from the displayed Table 4 values. **Do not silently replace the published figures.**

## Implications for the MR evidence chain
The F7 measured direction is consistent across the reported source quantities: irrigation depth **increased**, while water productivity **decreased**. But a valid event-by-event advice/action denominator is still absent, and treatment-control contrasts do not independently establish autonomous farmer adoption. The narrower numerical claim should be: **the −1.3/−1.4 difference is arithmetically explainable by rounding; the −0.1 conclusion and Table 5's −3.22 remain unverified**. This reduces one ambiguity without resolving the full primary-source reporting gate.

**Internal AI review:** arithmetic is deterministic and based on displayed original-publisher values; published depth may not capture all water terms and unrounded field records were not obtained. No independent data, causality, misconduct, human peer review, novelty or journal approval is claimed. **MAJOR REVISION / NO SUBMISSION**.

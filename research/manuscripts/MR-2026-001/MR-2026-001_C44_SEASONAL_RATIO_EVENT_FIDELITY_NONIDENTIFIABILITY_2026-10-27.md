# MR-2026-001 C44 — Constructive non-identifiability of event fidelity from seasonal irrigation totals

**2026-10-27 | Formal arithmetic counterexample using explicitly hypothetical schedules; NO new farm observations, no measured water savings, no validation of G/D/R/A.**

## Proposition
Let recommended irrigation events be the ordered triples `R={(day 1,10 mm),(day 8,10 mm),(day 15,10 mm)}`. Seasonal recommended depth is 30 mm. The seasonal applied/recommended depth ratio `ARIS = sum(applied depths)/30` does **not** uniquely determine event count, event timing, or event-specific dose. The proposition concerns mathematical identifiability only, not the exact empirical methods or data held by Lorite et al.

## Constructive proof by four hypothetical schedules
| Schedule | Applied events | Seasonal applied depth | ARIS | Exact recommendation-date-and-dose matches (of 3) |
|---|---|---:|---:|---:|
| A | (1,10), (8,10), (15,10) | 30 mm | 1.00 | 3 |
| B | (15,30) | 30 mm | 1.00 | 0 |
| C | (2,10), (9,10), (16,10) | 30 mm | 1.00 | 0 |
| D | (1,5), (8,15), (15,10) | 30 mm | 1.00 | 1 |

All four schedules have the **same seasonal ratio 1.00**, but they differ in event count (1 versus 3), dates and exact doses. The exact-match counts are illustrative under a **zero-tolerance one-to-one matching rule**; no field tolerance or optimality criterion is inferred. Thus the map from event sequences to their seasonal total is many-to-one. Even perfect agreement of total seasonal water **cannot establish event-level adherence**.

## Additional identification gates
1. Matching requires a defined advice timestamp, valid-from interval, plot/crop identifier, prescribed depth and whether advice was superseded or cancelled.
2. Independently observed farmer events need calibrated flow/volume or defensible proxy, event timestamp and a source provenance trail.
3. A matching algorithm must prespecify timing/depth tolerances, many-to-one matching rules, missing/extra events and ties; changing tolerances after seeing results is not validation.
4. Advice delivered, read, implemented and causally effective are distinct links; even exact event matches cannot by themselves prove *causal water savings* without a credible counterfactual.
5. This logical observation is consistent with existing adoption/adherence literature, including Lorite (2012), DOI 10.1007/s11269-012-0023-3. It **does not establish novelty** of a proposed G/D/R/A worksheet and is not a substitute for farmer event logs or blinded assessor validation.

## Editorial decision
Use this only as a transparent hypothetical illustration of a denominator/identifiability limit in the MR Perspective. Do not report the four schedules as field results, a trial, a model validation, or evidence that Lorite lacked event-level records. **MAJOR REVISION / NO SUBMISSION.**

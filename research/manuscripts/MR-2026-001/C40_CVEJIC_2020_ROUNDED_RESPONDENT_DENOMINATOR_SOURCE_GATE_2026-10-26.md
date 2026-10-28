# MR-2026-001 C40 — original-publisher Cvejić 2020 denominator consistency gate

**Date:** 26 October 2026. **Verdict:** CONDITIONAL ARITHMETIC CONSISTENCY ONLY; **NO VERIFIED RESPONDENT DENOMINATOR**. MR remains **MAJOR REVISION / NOT SUBMITTED**.

## Primary-source statements and unresolved unit discrepancy

Cvejić et al. (2020), *Agronomy* 10(9), 1238, DOI [10.3390/agronomy10091238](https://doi.org/10.3390/agronomy10091238), original publisher HTML: https://www.mdpi.com/2073-4395/10/9/1238 . The source states that the advisory system was implemented on **35 farms**, but elsewhere says **46 farmers** used emailed advice. Its 2020 telephone-feedback paragraph reports rounded percentages **83, 71, 49, 40, 11, 6, 17, 66**, and explicitly says **6% (two farmers)** were dissatisfied. These are *source statements*, not independently audited survey microdata.

## New exact integer consistency check

The reproducible script `analysis/cvejic_2020_denominator_consistency_gate.py` enumerates every common candidate denominator `n=2..46`, uses nearest-whole-percentage rounding (half-up), requires **2/n to round to 6%**, and checks whether *each* of the eight published percentages could be obtained by rounding some integer `k/n`.

**Conditional result:** `n=35` is the **only common denominator** in this bounded search satisfying all nine constraints. One compatible sequence of numerators, in source percentage order, is **29, 25, 17, 14, 4, 2, 6, 23**. For example, 29/35=82.857...% rounds to 83%; 2/35=5.714...% rounds to 6%. This is a **mathematical reconciliation of rounded aggregate statements, not a recovery of original respondent counts**.

The result relies on three **untested assumptions**: (1) the eight items share the same response base; (2) percentages were rounded to the nearest integer; (3) the relevant base is at most 46. The study's 35 *farms* cannot silently be equated with 35 individual *respondents*, particularly given the distinct 46-*farmers* phrase. Item nonresponse, question-specific eligibility or a source typographical error could change the base. The source does not provide individual answers or a reconciled 2020 respondent-flow table here. **Therefore, do not state '29 of 35 farmers adopted the system' as a verified fact.**

## Scientific interpretation and next steps

- The published **83% is self-reported use**, not event-level adherence, measured irrigation-water reduction, or an independently audited proportion of advice events followed.
- The publisher's modeled **25% irrigation savings** and **24% energy/CO₂ savings** must not be attributed to verified real-world adoption.
- The 35/46 unit inconsistency and item-specific respondent denominators remain an unresolved **source-methods gate**. Obtain the original questionnaire, participant-flow appendix, a correction or author clarification before any numerator/denominator claim.
- This new check improves **source-integrity precision**, not MR's originality or empirical validation. A source-locked Word must be regenerated after substantive manuscript edits. No journal submission is authorized.

**Computational method:** exact finite enumeration over candidate n and k; no external network, fake respondent rows, inferential significance or guessed survey records. `n=35` is conditional on the explicit rounding/common-base assumptions.

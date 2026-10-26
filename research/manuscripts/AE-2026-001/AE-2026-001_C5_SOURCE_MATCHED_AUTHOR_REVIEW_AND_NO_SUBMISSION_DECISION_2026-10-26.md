# AE-2026-001 C5 — source-matched scientific author review and publication decision

**Date:** 26 October 2026. **Stage:** human scientific author review candidate; **not submitted, not accepted, not published**. This is a research-administration packet produced with AI assistance, **not** a human referee report or the author's personal attestation.

**Latest internal AI editorial assessment (C6):** [direct functional comparison with documented countryatlas features](AE-2026-001_C6_DIRECT_COUNTRYATLAS_FUNCTIONAL_PRIOR_ART_AND_AI_EDITORIAL_GATE_2026-10-26.md) completed. The comparator already documents WDI vintage comparison, country selection, revision summaries and unit-rebasing warnings. AE's sign/rank/annualized-growth application is descriptive, not a validated new estimator. **Decision remains MAJOR REVISION / NO SUBMISSION**; no real head-to-head execution or independent ILO absolute employment validation was performed. This scientific gate does not alter the current manuscript source, so the Word artifact below remains source-matched.


## 26 October C7 source-code comparator addendum — Word rebuild required

Direct upstream R implementation of countryatlas::compare_vintages was inspected (not executed): the function computes **single-year indicator level revisions** and does not itself calculate AE's **two-endpoint annualised log-growth revision**, sign flips or rank stability. These are standard downstream calculations, not a new estimator or first-publication claim. [C7 source-code-level comparison](AE-2026-001_C7_COUNTRYATLAS_SOURCE_CODE_ESTIMAND_COMPARATOR_2026-10-26.md) records the precise boundary and lack of a matched numeric head-to-head benchmark. The **manuscript Discussion changed** in commit `7d1a13391f664036161697b25c067748cab6b4e9`; therefore the prior Word artifact **12628986033 is superseded**. Both on-push workflows completed **SUCCESS**: [run 40282047694](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40282047694), [artifact 12632282352](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40282047694/artifacts/12632282352), and [run 40282047856](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40282047856), [artifact 12633190015](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40282047856/artifacts/12633190015), from source commit 7d1a13391f664036161697b25c067748cab6b4e9. These are current Word review artifacts, **not** evidence of scientific ACCEPT or author attestation. This source clarification changes **no empirical results**. Scientific verdict remains **MAJOR REVISION / NO SUBMISSION**.

## Exact version for review

- Article: *Historical-Release Sensitivity of Agricultural Value Added per Worker in World Development Indicators: A Three-Vintage Fixed-Country Audit*.
- Canonical manuscript: `AE-2026-001_FIRST_FULL_EMPIRICAL_MANUSCRIPT_DRAFT_2026-10-25.md`, scientifically revised at commit **`1030146352c9f376d70db608e8074d847131e934`** and subsequently repaired for one literal escaped paragraph break at commit **`12edb0feb43d362872ae0851524d2246e4b9a842`**.
- **Latest exact source-matched Word after paragraph-break QA repair:** [GitHub Actions run 40271128021](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40271128021), completed **success**, [artifact 12628986033](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40271128021/artifacts/12628986033). Source SHA256 `59685b98bed260a083ece26772bf5dc8a0e2504661f14e8165a27aecb03bf5d0`; 8 Word tables. This repairs one literal escaped paragraph break without changing empirical results.
- **Do not substitute** earlier Word artifacts 12626566192, 12623863060 or 12620821908 for this revised manuscript.
- Source-locked independent numerical job: [run 40265858307](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40265858307), completed **success**, [artifact 12626477210](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40265858307/artifacts/12626477210). Both official 2024/2025 ZIP SHA256 gates and constant-2015-unit labels passed.

## Real empirical evidence and strict interpretation

1. Official 2024/2025/2026 WDI releases; 155 identical economies for 2000–2019. Six/six/ten growth-sign changes across adjacent and end-to-end vintage comparisons; 2024 lacks the 2023 endpoint required for a three-vintage 2000–2023 comparison.
2. Independent rank audit: 2024→2026 Spearman approximately 0.887; 26/155 economies had >1 log-percentage point/year historical-growth revision. This is descriptive sensitivity, not a causal economic shock.
3. **New original-archive auxiliary component audit:** the 2024→2025 **published value-added series** `NV.AGR.TOTL.KD` and **per-worker series** `NV.AGR.EMPL.KD` have 155 jointly observed economy pairs. Median absolute annual growth revision: 0.166532 log-pp for per-worker, about 0.0000000004 log-pp for published value added, and 0.093273 log-pp for the **algebraically implied** `L*=V/P` denominator. In 40/155 cases, the absolute numerator revision exceeds the absolute implied-denominator revision. Maximum algebraic identity residual: 2.43e-17. These are **not** independent ILO labor observations, an explanation of revision causes, or a new validated method.
4. Original source indicators and units are documented by World Bank metadata: https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.EMPL.KD and https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.TOTL.KD .

## Direct prior art and editorial decision

- Johnson et al. (2013), DOI 10.1016/j.jmoneco.2012.10.022, had already shown growth-estimate changes between statistical vintages.
- Filer et al. (2004) and Wolff et al. (2011), DOI 10.1111/j.1468-0297.2010.02408.x, are prior evidence of data-choice/revision sensitivity.
- **Direct existing WDI tool:** `countryatlas::compare_vintages()` already compares historical WDI releases, countries, revision sizes and unit mismatches: https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html . The current online documentation was inspected 26 October 2026; its original implementation date and peer-review status were not independently established.
- World Bank explicitly warns that historical WDI data are revised: https://datahelpdesk.worldbank.org/knowledgebase/articles/114939-how-are-revisions-managed .

**Internal AI science decision: MAJOR REVISION / NO SUBMISSION.** The real empirical case study may be appropriate for a narrowly framed *Data/Methods Note* if a journal actually accepts the article type and the author makes a genuine scientific contribution. No priority claim for comparing WDI vintages, a novel estimator, a causal attribution to ILO, or a new productivity theory survives. The source-specific contribution remains bounded and journal-level originality is **not established**. Do not submit merely because a Word file builds.

## Exact human-only release gates

| Gate | Status |
|---|---|
| Mojtaba Roozegar substantive scientific interpretation, revisions and approval of this exact manuscript | NOT ATTESTED |
| Corresponding author legal name, affiliation, institutional email if any and ORCID if actually held | NOT VERIFIED |
| Funding statement, COI declaration, AI use disclosure, ethics/data and rights statements | NOT ATTESTED |
| Journal, exact article type, fee/APC cap (default USD 0), licence, exclusivity and final cover letter | NOT SELECTED / NOT APPROVED |
| Manuscript ID or publisher receipt | NONE |

**Allowed:** further original-source comparison, independent labor-series reconciliation, scientific revision and human author review. **Not allowed:** journal submission, payment, legal/copyright declaration by AI, PR #1054 merge, live-site changes or representation as published scholarship.

## 26 October 2026 independent labor-series source-eligibility decision

The World Bank's official indicator `SL.AGR.EMPL.ZS` is **employment in agriculture as a percentage of total employment**, sourced from **ILO modelled estimates**, not a count of agricultural workers. Primary metadata: https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS and https://databank.worldbank.org/metadataglossary/world-development-indicators/series/SL.AGR.EMPL.ZS (consulted 26 October 2026). A percentage series **alone cannot independently validate the worker-count denominator** inferred by `L*=NV.AGR.TOTL.KD/NV.AGR.EMPL.KD`. An independent absolute employment estimate must share the same country definition, calendar years, employment coverage and vintage, with source-file checksum and unit checks. Multiplying the agriculture employment share by an incompatible labor-force or population series would introduce an unverified proxy and is **not authorized as validation**.

**Current decision:** ILO series identity and its percent unit were verified from official metadata; no ILO absolute agricultural employment counts or historical 2024/2025 archive-aligned count series were obtained in this check. The 155-economy `L*` algebraic decomposition remains descriptive and non-causal. This is a source-eligibility clarification, **not** a completed independent labor validation, an empirical manuscript result, or evidence of journal novelty.

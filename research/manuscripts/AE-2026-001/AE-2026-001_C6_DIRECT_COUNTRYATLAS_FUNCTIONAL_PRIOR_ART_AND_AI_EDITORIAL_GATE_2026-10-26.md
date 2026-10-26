# AE-2026-001 C6 — direct countryatlas functional prior-art benchmark and internal AI editorial gate

**Date:** 26 October 2026. **Reviewer:** ChatGPT, *internal AI methodological critic* (not a human referee, author or journal editor). **Decision: MAJOR REVISION / NOT SUBMISSION READY**. No manuscript ID.

## Actual comparator inspected

Primary public package documentation (accessed 26 October 2026):
- https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html
- Source link: https://github.com/PursuitOfDataScience/countryatlas/blob/main/R/worldbank.R

The documented `compare_vintages(indicator, vintages, year = NULL, countries = NULL)` accepts a WDI indicator, two or more releases, a comparison year and optional country subset. Its returned country-release table includes absolute/relative revisions and a summary with median absolute revision and shares exceeding 1%/10%; the package warns about vintage-specific **unit rebasing**. Its own documentation cites Johnson et al. (2013) on vintage-dependent growth estimates.

This is **documentation-level functional comparison**, not an independently executed head-to-head software benchmark. The date of first availability and peer-reviewed novelty status of countryatlas were not independently established.

| Claimed or potential contribution | Already documented in countryatlas? | AE-specific contribution, if any | Editorial status |
|---|---|---|---|
| Retrieve and compare historical WDI vintages | **Yes** | Uses official 2024/2025 archived files and 2026 API snapshot with SHA256 | Not a new method |
| Restrict comparisons to the same countries | **Yes** (`countries` argument) | Explicit 155-economy intersection with positive 2000/2019 endpoints | Application-specific implementation |
| Calculate country-level revision sizes | **Yes** | Adds annualized endpoint **growth-rate** revisions | Descriptive extension, not new estimator |
| Summarize median revision magnitude | **Yes** | Reports magnitude of **growth** revision, not merely level | Descriptive extension |
| Detect unit/rebasing changes | **Yes** | Checks fixed 2015 USD labels and archive SHA256 | Source-integrity application |
| Detect annualized growth sign reversals | **Not established by the inspected function reference** | 6/6/10 reversals and exploratory 0.5 log-pp margin | Specific documented output, no novelty priority claim |
| Measure cross-vintage growth ranking stability | **Not established by the inspected function reference** | Spearman 0.94996/0.91886/0.88697 | Standard statistic applied to one indicator |
| Compare published value added with algebraic implied denominator | **Not established by the inspected function reference** | 2024–2025 `L*=V/P` identity, 155 countries | Algebraic check, **not** independent ILO validation |
| Identify causes of revisions or causal productivity change | **No claim in documentation** | **Not achieved by AE either** | Cannot claim |

## Internal adversarial scientific assessment

**What is empirically real:** three official release snapshots, stable 155-economy comparison, reproducible 2000–2019 endpoint growth arithmetic, source-hash records, sign/rank/magnitude sensitivity and a clearly labelled algebraic numerator/residual decomposition. The 2024 archive lacks comparable 2023 observations. These are useful for reproducible *indicator-specific descriptive auditing*.

**Why acceptance is not justified now:** no documented head-to-head benchmark; standard statistics are not method invention; no independent employment count series aligned across vintages; source revision causes unidentified; no uncertainty model for correlated countries or releases; threshold 0.5 log-pp chosen post hoc; external generality untested; journal's actual Data/Methods Note article-type and fee route not verified; human substantive contribution and publication declarations pending.

**Disposition:** retain as **an original-source case-study draft**, not a first-ever WDI vintage method, new estimator or causal paper. Before author submission review, prioritize (1) an independently reproducible feature-matched countryatlas comparison on exactly the same indicator/years/vintages *if the package archives permit*, (2) a genuine absolute agriculture employment series with matching coverage and release, or explicit withdrawal of attribution claims, and (3) a publication fit decision for a transparent descriptive Data Note with truthful limitations. If no sufficient scientific contribution emerges, withhold submission rather than relabel a standard audit as novel.

**Human-only release gate:** Mojtaba Roozegar must personally confirm scientific contribution, exact version, authorship/affiliation, COI/funding/AI and rights statements, target journal/article type, cost cap and final cover letter. AI cannot attest or sign on his behalf. No submission, paid service, PR merge or live-site change was performed.

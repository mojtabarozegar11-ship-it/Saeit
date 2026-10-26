# AE-2026-001 C7 — source-code-level estimand comparison with countryatlas

**Date:** 26 October 2026. **Reviewer:** ChatGPT, internal AI methodological critic. **Decision:** MAJOR REVISION / NO SUBMISSION; direct source-code inspection clarifies an application-level difference, not methodological novelty.

## Actual independent inspection

Original upstream code inspected at [PursuitOfDataScience/countryatlas, R/worldbank.R](https://github.com/PursuitOfDataScience/countryatlas/blob/main/R/worldbank.R), compare_vintages function (source displayed 26 October 2026), with its [published reference manual](https://pursuitofdatascience.github.io/countryatlas/reference/compare_vintages.html). This is **source-code reading**, not execution of the R package, and does not establish the code's historical first release.

The function signature is compare_vintages(indicator, vintages, year = NULL, countries = NULL). The implementation:
- validates **one** indicator, multiple releases and **one** year when specified;
- retrieves a vintage-specific indicator panel, intersects the requested countries, and selects a common year when year=NULL;
- compares **single-year indicator levels** to the first vintage, with revision = value - baseline_value and rel_revision = revision/abs(baseline_value);
- reports median absolute and relative level revisions and shares exceeding 1%/10%, and warns about unit mismatch.

The inspected function does **not itself** calculate an endpoint **annualised log-growth rate** over two years, a growth-sign reversal, a cross-vintage growth-rank correlation or the three-vintage intersection cohort. These are standard downstream transformations, not proof of a new estimator; users can compute them from the package's underlying archived time-series retrieval functions.

## Estimand-specific comparison

| Question | countryatlas inspected function | AE source-locked analysis | Novelty verdict |
|---|---|---|---|
| Historical WDI releases | yes | yes | existing method |
| Same-country filter | yes | yes | existing method |
| Indicator level revisions for one year | yes | can be derived | existing method |
| Annualised 2000–2019 endpoint log-growth *revisions* | not implemented by this function | yes, on fixed 155-economy three-vintage cohort | indicator-specific downstream analysis; not a novel estimator |
| Cross-vintage sign/rank changes in endpoint growth | not implemented by this function | yes, source-backed 6/6/10 sign changes and Spearman 0.94996/0.91886/0.88697 | standard transformations; first-publication priority not established |
| Absolute employment independently sourced from ILO | no claim | not achieved | no independent denominator validation |
| Causal attribution of revisions | no claim | not achieved | unsupported |

## Scientific decision

The narrow difference between **single-year level revisions** and **two-endpoint annualised growth revisions** is now supported by the comparator's **actual implementation**, not just documentation. It should be described as an application-specific estimand rather than an original vintage-audit method. A fully matched numerical benchmark remains **not executed**: release API source 57 versus archived Excel snapshots may differ in availability and unit metadata, and no identical-source equality was tested. Neither scientific novelty nor author approval is established. This C7 finding may be used to sharpen the manuscript's Discussion without altering any empirical numerical result.

**No new WDI data, external peer review, causal result, paper submission, journal acceptance or Manuscript ID is claimed.**

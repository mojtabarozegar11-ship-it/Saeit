# Project 21 — Can We Trust the Origin of Our Research Data?

**Status:** Original editorial draft for the MojPlayWin research collection. Not yet included in the C12 signed archive or publicly published.  
**Audience:** Upper-secondary and undergraduate learners.  
**Estimated time:** 2–3 hours plus a seven-day observation period.  
**Materials:** A spreadsheet, notebook, and a small synthetic dataset created by the learner.

## Research question

How does a clear record of data origin, permissions and transformations change the reliability of a research conclusion?

## Why this project matters

A polished chart can conceal missing sources, copied values, undocumented edits or data collected without consent. This project teaches learners to distinguish *plausible-looking* data from *traceable* evidence. No personal data, participant recruitment, account access or third-party scraping is required.

## Hypothesis and variables

Hypothesis: A dataset with an explicit provenance record produces fewer unsupported conclusions during an independent review than an identical dataset with its provenance removed.

- Independent variable: provenance sheet present or absent.
- Dependent variable: number of claims an independent reviewer can verify from the supplied records.
- Controlled variables: dataset values, questions, time limit, scoring rubric and reviewer instructions.
- Confounders: reviewer experience, ambiguous wording and differences in interpretation.

## Create a safe synthetic dataset

Invent 14 daily observations of a fictional library's visits and book loans. Label every value **SYNTHETIC — NOT REAL CUSTOMER DATA**. Include the fields `day`, `visits`, `loans`, `weather_category` and `source_note`. Keep visits between 30 and 120, loans between 5 and 50, and loans no greater than visits. Record the random-number or manual generation rule. Do not present these numbers as observations of an actual library.

## Provenance ledger

For every column, document its definition, origin, units, creation date, any transformations, and the permission basis. Example:

| Field | Origin | Meaning | Transformation | Permission |
| --- | --- | --- | --- | --- |
| visits | learner-generated synthetic values | fictional daily entries | none | created by learner |
| loans | learner-generated synthetic values | fictional loans | none | created by learner |
| loan_rate | calculated from visits and loans | loans / visits | divide; flag zero denominator | derived from synthetic data |

Save a second copy with the ledger removed. The values in both copies must remain identical.

## Analysis protocol

1. Write three candidate claims: one descriptive, one comparative and one causal.
2. For each claim, identify exactly which rows and fields support it.
3. Calculate the mean visits, mean loans and the daily loan-rate range. Record spreadsheet formulas.
4. Have a reviewer, or the learner in a second timed session, assess both copies using the same rubric. Alternate the order to reduce order effects.
5. Score each claim: **2** = independently reproducible; **1** = partially traceable; **0** = not verifiable. Maximum score is 6 per copy.
6. Record discrepancies and whether the provenance ledger helped identify assumptions.
7. Explain why the synthetic data cannot establish a real-world causal relationship between weather and loans.

## Results worksheet

| Measure | Dataset with ledger | Dataset without ledger |
| --- | --- | --- |
| Claims fully reproduced (0–3) | | |
| Partial claims (0–3) | | |
| Unsupported claims (0–3) | | |
| Total rubric score (0–6) | | |
| Minutes spent verifying | | |

**Decision rule:** If the ledger improves reproducibility, describe the observed difference in this exercise only; do not generalize to all researchers or all datasets.

## Ethics and limitations

Use fictional values exclusively. Do not upload names, student records, location traces, emails or payment information. If the learner later adapts the project to real participants, obtain the relevant institutional approval and meaningful consent *before* collecting data. A single reviewer and a small synthetic sample cannot support population-level statistical inference. Provenance supports auditability but does not itself prove that an original measurement was accurate.

## Final deliverables

A synthetic CSV, a provenance ledger, the reproducible calculation sheet, the two-condition scoring table, a 300-word interpretation and a 100-word limitations statement. Include the exact creation method so another learner can reproduce the dataset without access to private information.

## Self-assessment rubric (20 points)

- Source and permission traceability: 0–4
- Reproducible calculations: 0–4
- Fair comparison of the two conditions: 0–4
- Distinction between correlation and causation: 0–4
- Ethical handling and explicit limitations: 0–4

## Further reading

- UK Data Service, *Research Data Management*: https://ukdataservice.ac.uk/learning-hub/research-data-management/
- FAIR Principles, Wilkinson et al., *Scientific Data* (2016), DOI: 10.1038/sdata.2016.18.
- U.S. Office of Research Integrity, *Responsible Conduct of Research*: https://ori.hhs.gov/

**Editorial note:** This is an original teaching exercise, not a report of an actual experiment. References are pointers for independent reading; no source text is reproduced.

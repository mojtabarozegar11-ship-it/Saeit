# MR-2026-001 C51 — Car et al. (2012) full-text denominator and group-label discrepancy audit

**27 October 2026 | Internal AI critical audit | NOT a verified publisher erratum, independent experiment, or author-approved conclusion.**

## Source provenance and access
- Car NJ, Christen EW, Hornbuckle JW, Moore GA (2012), *Computers and Electronics in Agriculture* 84:132–143, DOI https://doi.org/10.1016/j.compag.2012.03.003 .
- **Newly inspected:** author-uploaded full-text transcription on ResearchGate, https://www.researchgate.net/publication/257018309_Using_a_mobile_phone_Short_Messaging_Service_SMS_for_irrigation_scheduling_in_Australia_-_Farmers%27_participation_and_utility_evaluation . It identifies the uploaded text as contributed by coauthor Evan Christen (2018). Text is a secondary web extraction of an author-uploaded article, **not a verified publisher-page image**. The full original publisher PDF/table image must be compared before asserting an error in the published table.
- Original institutional abstract already established 72 trial irrigators, 45 returning information throughout the season, 13 for half and 14 never sending (45+13+14=72). These are *data-return duration categories*, not a count of advice-following events.

## Newly inspected Table 5, arithmetic and semantic tests
The web transcription of the paper's Table 5 (p. 140) shows the six count entries **26, 7, 3, 6, 15, 17**, associated with labels Close; Close with step; More; Much less; Stopped; Never sent. The printed total is **72**, but the six displayed counts sum to **74**. The displayed percentages 36, 9.7, 4.2, 8.3, 21, 24 sum to **103.2%**, not 100%. Using the stated denominator 72, the corresponding exact percentages are 36.1111%, 9.7222%, 4.1667%, 8.3333%, 20.8333%, and 23.6111%; ordinary rounding does not reconcile the count total.

The text immediately preceding Table 5 states that groups 1–3 constitute **68%** of full system participants, whereas the transcribed counts for groups 1–3 sum to **26+7+3=36**, or **50.0% of 72**. The abstract's season-long data-return count **45/72=62.5%** is a *different engagement definition* and cannot repair either discrepancy by substitution.

A separate **group-label/order mismatch** is visible: the narrative's numbered list calls group 4 *Stopped sending* and group 5 *Less throughout*, while the transcribed Table 5 lists group 4 *Much less* and group 5 *Stopped*. This could reflect an original editing error, a transcription/layout issue, or an unreported recoding; do not silently remap individuals.

## Newly inspected Table 6 and respondent denominator
The narrative preceding Table 6 (p. 140) says **40** active participants answered the open-ended behavior question. The transcribed Table 6 (p. 141) lists five counts **11, 10, 9, 8, 3**, totaling **41**; the table itself labels total **41** and percentages 27, 24, 22, 20, 7 (which approximate the 41-denominator proportions). The **40-versus-41** discrepancy must be resolved from a publisher-page image or clarification; no response fraction is inferred.

## Evidence interpretation
- **45/72 = 62.5%** is defensible only as *abstract-reported all-season return of irrigation/rainfall information*, not observed event-level adherence, farm water conservation, or randomized impact.
- The paper describes irrigator-entered run times and water-balance trajectories and interviews, which are more granular than an abstract-only study. But self-entered messages are not independent calibrated water-meter verification.
- **Do not** use the unreconciled Table 5 groups to estimate adherence, participation prevalence, or to validate G/D/R/A; do not pool with the different Table 6 respondent cohort.
- The author-uploaded full text is a material improvement in accessible evidence, but **the original publisher table image remains the decisive outstanding gate**. Do not present the arithmetic inconsistencies as a confirmed publisher erratum.

## Reproducible calculations
```python
t5=[26,7,3,6,15,17]
assert sum(t5)==74
assert sum([36,9.7,4.2,8.3,21,24])==103.2
assert sum(t5[:3])==36
assert 100*sum(t5[:3])/72==50.0
assert sum([11,10,9,8,3])==41
assert 45+13+14==72
```

**AI adversarial decision:** An author-uploaded full-text lead has exposed *at least two apparent numerical denominator contradictions and one label-order contradiction*. Treat as **UNRESOLVED SOURCE CONFLICT** until publisher image and final human author inspection. No new farm outcomes, DOI, independent human review, or submission. **MR MAJOR REVISION / NO SUBMISSION**.

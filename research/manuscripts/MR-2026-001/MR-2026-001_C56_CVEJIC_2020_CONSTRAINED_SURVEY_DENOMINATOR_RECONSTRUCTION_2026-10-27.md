# MR-2026-001 C56 — Cvejić 2020: constrained reconstruction of the 2020 survey denominator

**27 October 2026.** Independent integer-arithmetic audit of percentages in original MDPI publisher-indexed full-text excerpt, **not access to respondent-level data or proof of survey sample size**.

## Primary source
Cvejić, R., Černič-Istenič, M., Honzak, L., Pečan, U., Železnikar, Š., and Pintar, M. (2020). *Farmers Try to Improve Their Irrigation Practices by Using Daily Irrigation Recommendations—The Vipava Valley Case, Slovenia*. Agronomy 10(9), 1238. DOI https://doi.org/10.3390/agronomy10091238 . Publisher-indexed full-text sections 2.3 and 3 report: **35 initially interested farms**, **all farmers** providing 2020 telephone feedback, **83%** reported using IDSS, **71%** checking soil moisture, **49%** unchanged irrigation duration, **40%** more frequent/shorter irrigation, **11%** following reports without using IDSS, **6% (two farmers)** dissatisfied, **17%** partly satisfied and **66%** very satisfied. The paper separately refers to **46 farmers** using email advice in 2019, which cannot automatically be reconciled with 35 initial farms.

## Newly executed denominator constraint
Assume (a) all eight 2020 percentages use the **same integer respondent denominator n**, (b) each displayed percentage is rounded to the nearest whole percent, and (c) the 6% category really contains exactly two people. From 6% = round(200/n), possible n under ordinary rounding are approximately **31–36**. Testing each integer n in that interval against all other displayed percentages gives a **single joint solution n=35**, with the following reconstructed integer counts:

| Published rounded 2020 percentage | Reconstructed count / 35 | Unrounded percentage |
|---|---:|---:|
| 83% reported IDSS use | 29/35 | 82.857% |
| 71% viewed soil moisture | 25/35 | 71.429% |
| 49% duration unchanged | 17/35 | 48.571% |
| 40% more frequent shorter irrigation | 14/35 | 40.000% |
| 11% reports without IDSS use | 4/35 | 11.429% |
| 6% dissatisfied (two) | 2/35 | 5.714% |
| 17% partly satisfied | 6/35 | 17.143% |
| 66% very satisfied | 23/35 | 65.714% |

**Critical distinction:** n=35 is a **conditional arithmetic reconstruction**, not a publisher-verified 2020 response count. If questions had different denominators, nonresponse, weighting, altered rounding or different sets of participants, this joint solution does not establish the actual denominator. The text's 2019 **46 farmers** phrase remains unreconciled and cannot be used as the 2020 denominator.

## Consequence for MR
The 2020 83% figure is **farmer-reported use during telephone follow-up**, not objectively logged event-level compliance or measured water savings. Conditional on the common-denominator assumptions it is numerically compatible with **29/35**, but this must not be presented as an observed count unless original survey records or authors confirm it. The projected 25% water, 24% energy and 24% CO2 reductions remain simulations, not verified realized impacts.

**Scientific release:** original respondent denominator and the 2019 46-person statement remain open; MAJOR REVISION / NO SUBMISSION. No survey records, new experiment, independent field data, or human author approval were created.

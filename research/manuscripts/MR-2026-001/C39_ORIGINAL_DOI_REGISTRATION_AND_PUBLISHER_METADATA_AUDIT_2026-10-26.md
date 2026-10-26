# MR-2026-001 C39 — original DOI registration and publisher metadata integrity audit

**Checked:** 26 October 2026. **Scope:** 22 DOI references in the current 22-reference V5 Perspective. **Publication gate:** still **MAJOR REVISION / NOT SUBMITTED**.

## Actual metadata retrieval

Each of the 22 distinct cited DOI strings was individually queried through the **Crossref REST `/works/{doi}`** endpoint. **21 of 22** returned registered bibliographic metadata with normalized title-token overlap **1.00** against the corresponding manuscript reference line. The remaining DOI `10.48130/tia-0026-0009` did not return a usable Crossref result in this audit; the original publisher's [Technology in Agronomy article page](https://www.maxapress.com/article/doi/10.48130/tia-0026-0009) independently confirms the DOI, exact title, author list, volume 6 article e013 and publication date 10 October 2026. **No DOI was declared false solely because Crossref lacked a usable response.**

| Ref | DOI | Verified metadata route |
|---:|---|---|
| 1 | `10.1007/s11269-012-0023-3` | Crossref REST record resolved; registered title matched reference title |
| 2 | `10.1016/j.compag.2012.03.003` | Crossref REST record resolved; registered title matched reference title |
| 3 | `10.1002/ird.2337` | Crossref REST record resolved; registered title matched reference title |
| 4 | `10.1016/j.agwat.2021.107161` | Crossref REST record resolved; registered title matched reference title |
| 5 | `10.1016/j.agwat.2023.108590` | Crossref REST record resolved; registered title matched reference title |
| 6 | `10.1016/j.agwat.2024.108758` | Crossref REST record resolved; registered title matched reference title |
| 7 | `10.1007/s44279-025-00190-y` | Crossref REST record resolved; registered title matched reference title |
| 8 | `10.1038/s41598-025-26567-z` | Crossref REST record resolved; registered title matched reference title |
| 9 | `10.3390/agronomy10091238` | Crossref REST record resolved; registered title matched reference title |
| 10 | `10.1029/2023WR035810` | Crossref REST record resolved; registered title matched reference title |
| 11 | `10.3390/w11020252` | Crossref REST record resolved; registered title matched reference title |
| 12 | `10.17660/ActaHortic.2022.1335.81` | Crossref REST record resolved; registered title matched reference title |
| 13 | `10.1136/bmj.g1687` | Crossref REST record resolved; registered title matched reference title |
| 14 | `10.1186/1748-5908-2-40` | Crossref REST record resolved; registered title matched reference title |
| 15 | `10.48130/tia-0026-0009` | Official publisher DOI page confirms article; Crossref API did not return a record in this audit |
| 16 | `10.1016/j.agsy.2026.104867` | Crossref REST record resolved; registered title matched reference title |
| 17 | `10.1016/j.agwat.2024.108838` | Crossref REST record resolved; registered title matched reference title |
| 18 | `10.3390/w18172174` | Crossref REST record resolved; registered title matched reference title |
| 19 | `10.1002/ird.70098` | Crossref REST record resolved; registered title matched reference title |
| 20 | `10.3390/agronomy14010066` | Crossref REST record resolved; registered title matched reference title |
| 21 | `10.1002/ird.1887` | Crossref REST record resolved; registered title matched reference title |
| 22 | `10.3390/rs17111855` | Crossref REST record resolved; registered title matched reference title |

## Strict limits

- Crossref registration and title concordance verify **bibliographic identity only**. They do not establish that the cited paper's **full methods, numerical table, findings, ethics or causal claims** were independently checked.
- Car [2] original typeset Table 5 is **not yet inspected**; University of New England institutional page confirms its 72/45/13/14 abstract data but does not expose the disputed table image at https://rune.une.edu.au/handle/1959.11/14259 .
- Lorite [1] publisher bibliographic abstract provides ARIS LIAS ratios 0.23/0.94, but the detailed full-method observation denominator is not verified. Elia [12] original publisher abstract provides six-farm 24% seasonal water and 7% nitrogen contrasts, not event-level adherence.
- Amini [8] F7 published internal numerical contradictions remain unresolved; no corrected value is invented.
- This check is **not** a plagiarism-detection report, full-text review, systematic search, independent human peer review or publication novelty validation.

**Result:** **22/22 cited DOI identities accounted for** by 21 Crossref records and one original-publisher record; **0** full-text-only scientific gates cleared by metadata matching. No submission authorized.

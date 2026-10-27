# AE-2026-001 C37 — independent JavaScript re-execution of C36 from the source CSV

**27 October 2026 | Computational replication, not a new empirical result or a novel method.**

## Source
Read the branch-resident original WDI 2026 country CSV via GitHub contents API:
`research/manuscripts/AE-2026-001/AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`; Git blob SHA **d4910ff78219f9e5097c6301a6fbfa7752bbf4f9**. No API refresh or data imputation. The blob SHA is Git's identifier, **not** a newly computed SHA256 checksum.

## Fresh independent calculation
In an isolated JavaScript computation, parse quoted CSV fields, require both strictly positive 2000 and 2019 values, calculate `100*Math.log(P2019/P2000)/19`, sort by annualized log growth, and inspect one-based ranks 49, 79 and 109.

| Audit | Re-executed result |
|---|---|
| Nonaggregate CSV records | 217 |
| Positive complete endpoint pairs | 157 |
| Missing endpoint pairs | 60 |
| 109th position in hypothetical 217-record median | 109 |
| Sharp lower endpoint, observed rank 49 | **LBR 1.4239594820464043** |
| Observed 157-country median, rank 79 | **BGR 2.3555752946417114** |
| Sharp upper endpoint, observed rank 109 | **SWE 3.6898758409488392** |
| Positive observed rates | **132** |
| Nonpositive observed rates | **25** |

These independent JavaScript calculations agree, to displayed precision, with the existing C36 Python-oriented derivation. **No new statistical discovery is claimed**; this is a cross-implementation replication and consistency check. The 60 absent growth rates remain unidentified, and the positive-sign conclusion is limited to the hypothetical equal-economy 217-record finite frame. No inference about worker-weighted world agricultural productivity follows.

## Unclosed research gates
The historical 155-economy three-vintage analysis remains separate. Historical ILOSTAT release archives, direct countryatlas release matching, source-independence, novelty, and author confirmation remain open. No journal submission or author approval.

**Decision: AE MAJOR REVISION / NO SUBMISSION.**

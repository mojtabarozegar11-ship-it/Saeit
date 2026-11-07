# MR-2026-001 C144 — F7 displayed-cell rounding verification (2026-11-07)

Scope: reproducibility calculation on **published rounded cells**, not original field data, independent scientific review, or correction by source authors. Source: Amini et al. (2025), publisher Tables 4–5, PMCID PMC12660781, https://pmc.ncbi.nlm.nih.gov/articles/PMC12660781/ . The source figure caption for F7 is Fig. 12, not Fig. 7.

F7 published cells: DSS yield 48.9 t/ha and irrigation 1057.6 mm; control yield 45.6 t/ha and irrigation 764.9 mm. 1 t/ha = 1000 kg/ha; 1 mm = 10 m3/ha; WP = 100*yield(t/ha)/irrigation(mm). DSS WP = 4.6236762481 kg/m3; control WP = 5.9615636031 kg/m3; difference = -1.3378873550 kg/m3; control-relative difference = -22.4418867943%.

For independently rounded displayed inputs, take yield within ±0.05 t/ha and depth within ±0.05 mm. Let R=100*((Yd/Id)/(Yc/Ic)-1). The monotonic extrema are:
- Lower: (Yd,Id,Yc,Ic)=(48.85,1057.65,45.65,764.85) -> -22.6147689739%.
- Upper: (48.95,1057.55,45.55,764.95) -> -22.2686063583%.

This is a **rounding envelope, not a statistical confidence interval**. It does not resolve source percentage-labelled -3.22 or conclusion -0.1 kg/m3; retain unresolved pending raw calculation sheets or source-author clarification. No new field data, no independent acceptance, no journal submission or publication is claimed.

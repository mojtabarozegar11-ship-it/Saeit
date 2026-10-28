#!/usr/bin/env python3
"""Recalculate Amini et al. (2025) Tables 4-5 from rounded published values.
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12660781/
No original individual-farm observations, precision estimates, or causal tests are available.
"""
import json
rows=[("F1",306.9,306.9,3.1,3.1,0),("F2",721.5,721.5,.8,.8,0),
("F3",1064.7,1223.1,8.7,7.4,1.17),("F4",1460.2,1234.4,6.3,6.5,-2.3),
("F5",363.2,616.8,8.4,4.6,3.87),("F6",739.3,1048.3,.5,.3,1.45),
("F7",1057.6,764.9,4.6,6.,-3.22),("F8",1413.8,1455.,.7,.6,9.15)]
out=[]
for farm,ir_t,ir_c,wp_t,wp_c,t5 in rows:
    delta=round(wp_t-wp_c,2)
    wp_pct=round(100*(wp_t/wp_c-1),2)
    out.append({"farm":farm,"irrigation_treatment_mm":ir_t,"irrigation_control_mm":ir_c,
      "irrigation_delta_mm":round(ir_t-ir_c,1),
      "irrigation_reduction_pct":round(100*(ir_c-ir_t)/ir_c,2),
      "wp_treatment_kg_m3":wp_t,"wp_control_kg_m3":wp_c,
      "wp_delta_kg_m3":delta,"wp_relative_change_pct":wp_pct,
      "table5_labeled_wp_percent":t5,
      "table5_vs_table4_discrepancy_over_0_5_percentage_point":abs(wp_pct-t5)>0.5})
assert len(out)==8
assert next(r for r in out if r["farm"]=="F7")["wp_delta_kg_m3"]==-1.4
assert next(r for r in out if r["farm"]=="F5")["irrigation_reduction_pct"]==41.12
assert sum(r["table5_vs_table4_discrepancy_over_0_5_percentage_point"] for r in out)==6
print(json.dumps({"source":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12660781/",
 "caution":"Rounded source table values; Table 5's labeled percent is not reconcilable with Table 4 for six sites at >0.5 pp; do not infer original unrounded observations.",
 "farms":out},indent=2))

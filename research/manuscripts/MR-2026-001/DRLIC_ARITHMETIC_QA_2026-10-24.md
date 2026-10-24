# MR-2026-001 — Independent arithmetic audit of Ding & Du
Checked 2026-10-24. Underlying source: [preprint §6.3.2 and §6.8](https://arxiv.org/html/2304.01435). Calculations verified independently in Python; this is arithmetic consistency checking, **not** independent replication of experiments or model outputs.

| Reported/assumed inputs | Independent arithmetic | Interpretation |
|---|---:|---|
| 195.26 billion gallons × 10.21% | 19.936046 billion gallons → **19.94** | Matches paper's annual projected ET-comparator saving; **P** nationwide extrapolation, not field-measured |
| 195.26 × 3.93% | 7.673718 billion gallons → **7.67** | Matches projected sensor-comparator saving; **P** |
| $11.30 per tree per month × 9.52% | **$1.07576** → $1.08 | Based on short field percentage plus assumed monthly unit cost |
| $1.07576 × 100 trees/acre | **$107.576** → $108 | Projected monthly saving per acre |
| $1.07576 × 600 trees/6-acre region | **$645.456** | Paper quotes **$648** based on rounded $1.08/tree × 600; rounding difference **$2.544** |
| $294.80 / $645.456 | **0.4567 months** | Conditional payback estimate; omits uncertainty, operating costs and transferability |

**Quality flag:** The arithmetic matches within stated rounding, but scaling a **15-day, six-tree** experiment to annual or commercial-orchard economics requires explicit caveats. The 195.26-billion-gallon national denominator is a paper-supplied assumption and was not independently validated. No raw field actuation logs or direct water-meter data were reprocessed. Companion executable: `verify_ding_du_arithmetic.py`.

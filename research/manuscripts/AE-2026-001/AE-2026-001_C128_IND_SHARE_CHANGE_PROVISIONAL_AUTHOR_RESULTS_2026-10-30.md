# AE-2026-001 | C128 India agriculture-share year-to-year descriptive result
Date 2026-10-30. Status: PROVISIONAL / AUTHOR REVIEW, not an inferential finding.

## Inputs (from previously transcribed WDI figures; official raw responses NOT archived)
| Year | SL.AGR.EMPL.ZS: agricultural employment (% of total employment) | NV.AGR.TOTL.ZS: agriculture, forestry and fishing value added (% GDP) |
|---|---:|---:|
| 2023 | 43.51358112 | 17.65653893 |
| 2024 | 42.35477389 | 17.57357995 |

## Reproducible descriptive arithmetic
- Employment-share change 2024 minus 2023: **−1.15880723 percentage points**.
- Value-added-share change: **−0.08295898 percentage points**.
- Share gap E−V: 2023 **25.85704219 pp**; 2024 **24.78119394 pp**; change **−1.07584825 pp**.
- Dimensionless ratio E/V: 2023 **2.46444568**; 2024 **2.41013920**; change **−0.05430648**.
- Definitions: E=SL.AGR.EMPL.ZS, V=NV.AGR.TOTL.ZS. Ratios are **shares**, not worker productivity, wage inequality, causal effects or real output per employee.

## Reproduction and evidence gate
```python
data={2023:(43.51358112,17.65653893),2024:(42.35477389,17.57357995)}
for y,(e,v) in data.items():
    print(y,round(e-v,8),round(e/v,8))
print("gap_change_pp",round((data[2024][0]-data[2024][1])-(data[2023][0]-data[2023][1]),8))
```
**BLOCKED for scholarly submission** until exact World Bank API JSON or CSV for each series and date, indicator definitions, vintage/revision date, country code and provenance hashes are archived and independently reconciled with ILOSTAT's appropriate series. No fabricated confidence interval or causal conclusion. Sources to retrieve: https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS?locations=IN and https://data.worldbank.org/indicator/NV.AGR.TOTL.ZS?locations=IN . No VPS/factory activity.
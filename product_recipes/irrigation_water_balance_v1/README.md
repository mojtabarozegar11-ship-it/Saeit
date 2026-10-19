# Irrigation Water Balance Toolkit — v1.0.0

**Private technical product candidate. Not published or licensed for public redistribution.** New original offline Python calculator, with measured functional regression tests. Intended for the crop and water-management category of Zomorod Melal after independent scientific, rights and storefront QA.

## Scientific calculation

For a user-supplied reference evapotranspiration ETo (mm/day) and crop coefficient Kc, the single-coefficient approach gives ETc = ETo × Kc. Over d days, the simplified net irrigation depth is max(0, ETc × d − effective rainfall × d − measured soil-water credit). Gross depth is net depth divided by a user-measured irrigation application efficiency fraction in (0,1]. A millimetre over one hectare equals 10 cubic metres; gross volume is gross depth × area (ha) × 10.

**Example:** ETo=5, Kc=1.2, effective rainfall=1 mm/day, soil credit=0, efficiency=0.8, period=7 days, area=2 ha. Crop ET=42 mm; net irrigation=35 mm; gross depth=43.75 mm; **gross volume=875 m³**. Illustrative only; not a field prescription.

## Run and test

```bash
python3 calculator.py --eto 5 --kc 1.2 --rain 1 --soil-credit 0 --efficiency 0.8 --days 7 --hectares 2
python3 -m unittest discover -v -p 'test_*.py'
```

Requires Python 3.8+ standard library; no network, external API, payment, telemetry or file writes. JSON is printed to stdout. Invalid or non-finite values are rejected. No input values are inferred from weather forecasts or third-party data.

## Evidence, limits and rights

Source: Allen, Pereira, Raes and Smith (1998), *Crop evapotranspiration*, FAO Irrigation and Drainage Paper 56, Chapter 5, Equation 56: https://www.fao.org/4/x0490e/x0490e0a.htm . The cited source supports ETc=Kc×ETo; the remaining water-balance arithmetic is an explicit simplified assumption. The tool does not model runoff, salinity, leaching, water stress, irrigation scheduling, capillary rise or crop-specific field safety. It is not independently field validated. Original code contains no copied third-party code, images or datasets. The rights holder must separately approve a redistribution license before free storefront activation. A passing technical ZIP test does not imply a FactoryReleaseManifest, store record or public URL.

# Farm Enterprise Economics Toolkit — Practical User Guide

**Edition 1.3 · Offline tool · Customer documentation candidate**

This guide teaches a farm owner, agricultural adviser or small-business manager
how to prepare a consistent enterprise budget, calculate operating contribution,
and interpret the tool's break-even and sensitivity results. It assumes no
programming experience. All input examples are **invented teaching numbers**,
not market quotations, farm observations or income promises.

> **Release status:** This document belongs to a private product candidate.
> It is not a sales licence, quality certificate or assurance that the product
> has passed the factory's separate commercial-release checks.

## 1. What the toolkit can answer

- How much revenue and contribution does each farm activity generate from
  quantities **sold**, prices actually received and costs allocated to it?
- At the stated selling price, how many units must be sold to cover the stated
  variable costs, selling fees and fixed costs?
- What selling price would cover those same costs at the stated sales volume?
- How would profit change in specified volume, price and variable-cost
  scenarios, both for one activity and for the farm as a whole?

The toolkit is **not** a bookkeeping system, tax calculator, cash-flow forecast,
market-price service, yield forecast or investment recommendation. In
particular, operating profit here excludes depreciation, interest, tax,
capital spending and changes in working capital.

## 2. Before opening the program: prepare a budget sheet

Choose one time period (for example, a calendar year or one production cycle)
and one currency for **every** value. Do not mix months with years or units
such as kilograms with tonnes. Gather this information for each activity:

| Input name | What to record | Avoid this mistake |
| --- | --- | --- |
| `name` | A distinct activity name, such as `Apple Orchard` | Using the same name twice |
| `units_sold` | Quantity expected to be **sold** in the period | Entering harvested volume when some harvest remains unsold |
| `unit_price` | Average amount received per unit sold | Entering a retail price when sales are at the farm gate |
| `variable_cost_per_unit` | Cost incurred per unit sold, in the same unit as the quantity | Mixing cost per hectare with price per kilogram |
| `allocated_fixed_cost` | Period fixed costs allocated to this one activity | Charging the same shared overhead in full to several activities |
| `selling_fee_percent` | Sales commission or similar fee as a percent of gross sales | Entering `0.05` when you mean **5%**; enter `5` |

Keep a dated record of where your estimates came from. If you do not know a
cost, research or measure it **before** using the result for a real decision.
Do not type credentials, payment cards or customer names into the example
dataset; the calculator does not need them.

## 3. Start the toolkit — Windows, macOS or Linux

The current edition requires **Python 3.8 or newer**, installed separately.
There are no paid dependencies or online accounts. The calculator itself
works offline after installation.

### Recommended: guided entry, without editing a data file

1. Put `guided_start.py` and `calculator.py` together in a folder where you
   have permission to create files. They must come from the **same toolkit
   edition**.
2. Open a terminal or command prompt in that folder and enter:

   ```sh
   python guided_start.py
   ```

   On systems that use `python3`, use `python3 guided_start.py` instead.
3. Answer the questions with your **own** values. A fee of `5` means 5%,
   and decimals use a dot. The wizard validates numbers, fees, distinct
   enterprise names and the complete budget using the same calculation engine
   as the manual option.
4. Review the result summary. Type uppercase `YES` to authorize the local
   file creation; any other reply cancels without creating a report folder.
5. Open `management-report.html` in the new `farm-budget-...` folder. The
   folder also contains your saved input and JSON/CSV analysis files. Each
   confirmed run creates a **different folder** so older budgets remain intact.

The wizard does not upload inputs, connect to a payment service, or publish a
product. Its figures are scenarios derived solely from your assumptions.

### Advanced: manual JSON entry

1. Place `calculator.py` and `example_inputs.json` together in a folder that
   you own and can write files into.
2. Make a copy of `example_inputs.json`, named `my_farm.json`. Keep the original
   untouched for reference.
3. Open `my_farm.json` in an ordinary text editor. Replace **all** example
   quantities, prices, costs and names. Preserve the quotation marks,
   commas, square brackets and braces. Use a dot for decimals (`3.50`, not
   `3,50`), and do not add a currency sign before numbers.
4. Open a terminal or command prompt **in that folder** and run the command
   below. If your system calls Python `python3`, replace `python` with
   `python3`.

   ```sh
   python calculator.py my_farm.json --json-output results.json --csv-output scenarios.csv --three-factor-csv-output joint-stress.csv --html-output management-report.html
   ```

5. Open `management-report.html` with a browser. It is a **local file**, so
   you need not upload your figures or have an Internet connection.
6. Keep `my_farm.json` together with the generated files in a private folder
   and make your own backup. The program does not store a cloud copy.

**Important:** Running the command again with the same output names replaces
the earlier reports. Use a new dated folder for each budget version.

## 4. Walk-through using the supplied fictional sample

The sample contains two independent enterprises, both expressed in USD:

| Metric | Illustrative Orchard | Illustrative Greenhouse |
| --- | ---: | ---: |
| Units sold | 1,000 | 750 |
| Selling price per unit | 10.00 | 8.00 |
| Variable cost per unit | 4.00 | 3.50 |
| Allocated fixed cost | 3,000.00 | 2,400.00 |
| Selling fee | 5% | 3% |
| Revenue | 10,000.00 | 6,000.00 |
| Fee + variable + fixed costs | 7,500.00 | 5,205.00 |
| **Operating profit** | **2,500.00** | **795.00** |
| Continuous break-even quantity | 545.4545… | 563.3802… |
| Whole-unit break-even threshold | 546 | 564 |

The hypothetical farm therefore has **16,000.00** in revenue,
**12,705.00** in operating costs, and **3,295.00** in operating profit
*before* the exclusions listed in Section 1. These are arithmetic checks
against the included sample, **not expected profits for any real farm**.

### Understand the two break-even quantities

The mathematical threshold can include a fraction of a unit. If apples are
sold by the tonne or milk by the litre, consult
`break_even_quantity_continuous` instead of treating the whole-unit ceiling as
your physical target. If you sell indivisible boxes or animals, the rounded-up
`break_even_units` may be more practical.

If unit contribution is zero or negative with positive fixed costs, the
break-even quantity is unavailable: selling more of the same activity under
those assumptions cannot pay off fixed costs. This is **not** a software error.

## 5. Interpreting the management report

**Revenue:** units sold multiplied by the received unit price.

**Contribution margin:** revenue minus variable costs and selling fees. It is
the amount available to cover allocated fixed costs.

**Operating profit:** contribution margin minus the fixed costs allocated to
that activity; it is not necessarily money in the bank.

**Margin of safety:** the modeled distance between sold volume and the
break-even volume. A negative value means the modeled activity is below its
break-even volume under the inputs used. A positive value does not prove that
future demand will materialize.

**Price needed to break even:** the price that would cover the modeled costs
at the entered quantity. It does not say whether buyers will pay that price.

### The sensitivity tables

- The **nine-scenario table** varies sold volume by 80%, 100% or 120% and
  selling price by 90%, 100% or 110%, using the same multipliers for every
  activity in the whole-farm table.
- The **27-scenario table** also varies per-unit variable cost by 90%, 100%
  or 110%. It helps explore a combination such as weaker sales and dearer
  inputs, not the probability of that combination.
- Fixed costs and selling-fee percentages remain unchanged in these scenarios.
  The midpoint (100% volume, 100% price, 100% variable cost) should equal the
  baseline operating profit.

Do not call the largest scenario value a forecast. A scenario is a
**question you ask the model**, not evidence that the outcome will occur.

## 6. What each exported file contains

| File | Practical use |
| --- | --- |
| `results.json` | Full structured calculations and an input fingerprint for reproducibility |
| `scenarios.csv` | The nine two-factor scenarios per enterprise for spreadsheets |
| `joint-stress.csv` | The 27 three-factor scenarios per enterprise **and** for the whole farm; use the `scope` column to tell them apart |
| `management-report.html` | A self-contained report to read or print in a web browser |

CSV is quoted for spreadsheet safety. If your spreadsheet uses a comma as its
decimal separator, **import** the CSV and select a dot-decimal locale rather
than silently converting numbers. Do not add rows with `scope=enterprise` to
the corresponding `scope=portfolio` rows: the portfolio already includes the
enterprises, so that would count them twice.

The JSON includes exact per-unit values for fine-priced commodities. The HTML
report uses those precision-preserving values; money totals are shown to two
decimal places. For currencies or products with special minor units, this
display choice is not a legal rounding standard.

## 7. How to verify a saved calculation

Keep the original input file. To recheck an existing saved JSON report against
that input **without rewriting either file**:

```sh
python calculator.py my_farm.json --verify-json results.json
```

A successful check confirms that the saved report matches the current code's
recalculation of that input. It does **not** verify market prices, prove who
made the input file, supply a digital signature or replace external review.

## 8. Common problems and safe recovery

| Problem | What to check |
| --- | --- |
| `python` command not found | Install an appropriate supported Python version; on some systems use `python3` |
| `INPUT_ERROR: invalid number` | Use plain numbers and dot decimals; remove currency symbols or thousands separators |
| `INPUT_ERROR: enterprise names must be unique` | Give every activity a different name, including after ignoring letter case |
| Report has unexpectedly high profit | Check whether unsold goods were counted as sold or shared fixed costs omitted |
| Break-even is unavailable | Check for zero/negative unit contribution, 100% sales fee or zero activity volume |
| No new HTML report appears | Check that the requested output folder exists and is writable; read the terminal error |
| `stored report does not match` | Confirm the exact old input, calculator edition and report belong together; do not simply discard the mismatch |

The program has safeguards against writing output over its input or assigning
the same file name to several formats. Nevertheless, protect your original
budget and reports with independent backups.

## 9. Checklist before using results for an actual decision

- [ ] All activities use the **same period** and a consistent currency.
- [ ] Each activity's selling unit matches the corresponding cost unit.
- [ ] Sold quantity excludes unsold or spoiled production.
- [ ] Fixed costs are allocated once and supported by records.
- [ ] Selling fees and variable costs reflect the actual sales channel.
- [ ] The baseline and stress tables were read together; no scenario was
      mistaken for a forecast or buyer commitment.
- [ ] Depreciation, financing, taxes, inventories, investment and cash timing
      were considered **outside this model** where relevant.
- [ ] Inputs and outputs were saved privately with dates and backups.
- [ ] A competent professional reviewed material investment decisions and
      any uncertain accounting assumptions.

## 10. Boundaries of this edition

This calculator uses 1–100 distinct enterprises, nonnegative quantities and
costs, and selling fees between 0% and 100%. Its internally documented
precision and magnitude limits protect against extreme inputs. It neither
imports current commodity prices nor automatically learns from markets.

The files are intended for offline economic planning and education.
Commercial terms, after-sale support contact, distribution method and
independent quality clearance must be supplied and verified **before** the
factory releases the product to customers.

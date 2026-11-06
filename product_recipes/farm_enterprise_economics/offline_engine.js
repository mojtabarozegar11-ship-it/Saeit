/* Farm Enterprise Economics: offline, deterministic browser arithmetic.
 * User assumptions only. Exact BigInt fractions avoid floating-point money errors.
 * Browser input is plain decimal (no exponents), at most 30 decimal places;
 * the Python CLI remains available for other numeric notation.
 */
(function (root) {
  'use strict';
  const ONE = { n: 1n, d: 1n };
  const ZERO = { n: 0n, d: 1n };
  const HUNDRED = { n: 100n, d: 1n };
  const MAX = { n: 100000000000000000000n, d: 1n };
  const LIMIT = 100;
  const CASH_FIELDS = ['cash_receipts', 'operating_payments', 'asset_purchases',
    'loan_receipts', 'loan_repayments', 'other_payments'];

  function gcd(a, b) {
    a = a < 0n ? -a : a;
    b = b < 0n ? -b : b;
    while (b) { const t = a % b; a = b; b = t; }
    return a || 1n;
  }
  function fraction(n, d = 1n) {
    if (d === 0n) throw new Error('Division by zero');
    if (d < 0n) { n = -n; d = -d; }
    const g = gcd(n, d);
    return { n: n / g, d: d / g };
  }
  function add(a, b) { return fraction(a.n * b.d + b.n * a.d, a.d * b.d); }
  function sub(a, b) { return fraction(a.n * b.d - b.n * a.d, a.d * b.d); }
  function mul(a, b) { return fraction(a.n * b.n, a.d * b.d); }
  function div(a, b) {
    if (b.n === 0n) throw new Error('Division by zero');
    return fraction(a.n * b.d, a.d * b.n);
  }
  function cmp(a, b) {
    const delta = a.n * b.d - b.n * a.d;
    return delta < 0n ? -1 : delta > 0n ? 1 : 0;
  }
  function decimal(raw, field, min = ZERO, max = MAX) {
    if (raw === null || raw === undefined || typeof raw === 'boolean') {
      throw new Error(field + ': a finite decimal number is required');
    }
    // JSON.parse can silently round large integer and all fractional Number
    // tokens before they reach this exact engine. Allow only safe JSON integers;
    // quote all other decimal amounts to preserve every entered digit.
    if (typeof raw === 'number' && !Number.isSafeInteger(raw)) {
      throw new Error(field + ': quote fractional or large JSON amounts as decimal strings');
    }
    const text = String(raw).trim();
    if (text.length > 64 || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) {
      throw new Error(field + ': enter a plain decimal number (no scientific notation)');
    }
    const negative = text[0] === '-';
    const unsigned = text.replace(/^[+-]/, '');
    const parts = unsigned.split('.');
    const places = (parts[1] || '').length;
    if (places > 30) throw new Error(field + ': maximum 30 decimal places in browser');
    const n = BigInt((parts[0] || '0') + (parts[1] || '')) * (negative ? -1n : 1n);
    const value = fraction(n, 10n ** BigInt(places));
    if (cmp(value, min) < 0 || cmp(value, max) > 0) {
      throw new Error(field + ': outside allowed range');
    }
    return value;
  }
  function scaledRounded(value, places, up = false) {
    const factor = 10n ** BigInt(places);
    let numerator = value.n * factor;
    const negative = numerator < 0n;
    if (negative) numerator = -numerator;
    let quotient = numerator / value.d;
    const remainder = numerator % value.d;
    if ((up && remainder > 0n) || (!up && (remainder * 2n > value.d ||
        (remainder * 2n === value.d && quotient % 2n !== 0n)))) quotient += 1n;
    return negative ? -quotient : quotient;
  }
  function format(value, places = 2, up = false) {
    const scaled = scaledRounded(value, places, up);
    const negative = scaled < 0n;
    const digits = (negative ? -scaled : scaled).toString().padStart(places + 1, '0');
    const display = places ? digits.slice(0, -places) + '.' + digits.slice(-places) : digits;
    // Decimal.quantize retains a negative sign when a tiny loss rounds to -0.00.
    return (negative || value.n < 0n ? '-' : '') + display;
  }
  function exact(value) {
    // All unrounded fields passed to exact() have a terminating base-10 expansion.
    let denominator = value.d;
    let twos = 0, fives = 0;
    while (denominator % 2n === 0n) { denominator /= 2n; twos += 1; }
    while (denominator % 5n === 0n) { denominator /= 5n; fives += 1; }
    if (denominator !== 1n) throw new Error('Nonterminating decimal');
    const precision = Math.max(twos, fives);
    return format(value, precision).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  }
  function ceilNonnegative(value) {
    if (value.n < 0n) throw new Error('Expected nonnegative');
    return (value.n + value.d - 1n) / value.d;
  }
  function safeInt(value) {
    return value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value.toString();
  }
  function nameOf(row) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) throw new Error('Enterprise must be an object');
    const name = String(row.name || '').trim();
    if (!name || name.length > 120 || !/^[\p{L}\p{N}]/u.test(name) || /[\u0000-\u001f\u007f]/.test(name)) {
      throw new Error('Enterprise name must start with a letter or digit, with no control characters');
    }
    return name;
  }
  function optional(row, key, positive = false) {
    if (!(key in row) || row[key] === '') return null;
    const value = decimal(row[key], key);
    if (positive && value.n === 0n) throw new Error(key + ': must be positive');
    return value;
  }
  function enterprise(entry) {
    const name = nameOf(entry);
    const quantity = decimal(entry.units_sold, name + '.units_sold');
    const price = decimal(entry.unit_price, name + '.unit_price');
    const variable = decimal(entry.variable_cost_per_unit, name + '.variable_cost_per_unit');
    const fixed = decimal(entry.allocated_fixed_cost, name + '.allocated_fixed_cost');
    const feePercent = decimal(entry.selling_fee_percent === undefined ? '0' : entry.selling_fee_percent,
      name + '.selling_fee_percent', ZERO, HUNDRED);
    const fee = div(feePercent, HUNDRED);
    const contributionUnit = sub(mul(price, sub(ONE, fee)), variable);
    const revenue = mul(quantity, price);
    const fees = mul(revenue, fee);
    const variableTotal = mul(quantity, variable);
    const contribution = sub(sub(revenue, fees), variableTotal);
    const profit = sub(contribution, fixed);
    const cost = add(add(fees, variableTotal), fixed);
    const reachable = cmp(contributionUnit, ZERO) > 0;
    const threshold = reachable ? ceilNonnegative(div(fixed, contributionUnit)) : null;
    const priceThreshold = quantity.n > 0n && cmp(fee, ONE) < 0
      ? format(div(add(variable, div(fixed, quantity)), sub(ONE, fee)), 2, true) : null;
    const safety = threshold === null ? null : sub(quantity, fraction(threshold));
    const land = optional(entry, 'land_area_hectares', true);
    const water = optional(entry, 'irrigation_water_m3');
    const result = {
      name, units_sold: exact(quantity), unit_price: format(price),
      variable_cost_per_unit: format(variable), allocated_fixed_cost: format(fixed),
      selling_fee_percent: exact(feePercent), sales_revenue: format(revenue),
      selling_fees: format(fees), variable_cost_total: format(variableTotal),
      total_cost: format(cost), contribution_margin_total: format(contribution),
      contribution_per_unit: format(contributionUnit), operating_profit: format(profit),
      break_even_units: threshold === null ? null : safeInt(threshold),
      break_even_reachable: reachable,
      break_even_unit_price_at_planned_volume: priceThreshold,
      margin_of_safety_units: safety === null ? null : exact(safety),
      margin_of_safety_percent: safety === null || quantity.n === 0n
        ? null : format(mul(div(safety, quantity), HUNDRED)),
      land_area_hectares: land === null ? null : exact(land),
      irrigation_water_m3: water === null ? null : exact(water),
      units_sold_per_hectare: land === null ? null : format(div(quantity, land), 4),
      operating_profit_per_hectare: land === null ? null : format(div(profit, land)),
      units_sold_per_irrigation_m3: water === null || water.n === 0n
        ? null : format(div(quantity, water), 4),
      operating_profit_per_irrigation_m3: water === null || water.n === 0n
        ? null : format(div(profit, water))
    };
    return { result, numbers: { quantity, price, variable, fixed, fee, revenue, cost, profit, contribution, land, water } };
  }
  function cashflowPlan(plan) {
    if (!plan || typeof plan !== 'object' || Array.isArray(plan)) {
      throw new Error('cashflow_plan must be an object');
    }
    const cents = (raw, name) => {
      const value = decimal(raw, name);
      if (mul(value, fraction(100n)).d !== 1n) {
        throw new Error(name + ': at most two monetary decimal places');
      }
      return value;
    };
    const opening = cents(plan.opening_cash, 'cashflow.opening_cash');
    if (!Array.isArray(plan.months) || plan.months.length !== 12) {
      throw new Error('cashflow.months must contain exactly twelve months');
    }
    let balance = opening, minimum = null, firstNegative = null, operatingTotal = ZERO;
    const months = plan.months.map((row, index) => {
      if (!row || typeof row !== 'object' || Array.isArray(row)) {
        throw new Error('cashflow month must be an object');
      }
      const values = {};
      for (const field of CASH_FIELDS) values[field] = cents(row[field], 'cashflow.month_' + (index + 1) + '.' + field);
      operatingTotal = add(operatingTotal, sub(values.cash_receipts, values.operating_payments));
      const change = sub(add(values.cash_receipts, values.loan_receipts),
        add(add(values.operating_payments, values.asset_purchases),
          add(values.loan_repayments, values.other_payments)));
      balance = add(balance, change);
      if (minimum === null || cmp(balance, minimum) < 0) minimum = balance;
      if (firstNegative === null && cmp(balance, ZERO) < 0) firstNegative = index + 1;
      const rowOutput = { month: index + 1 };
      for (const field of CASH_FIELDS) rowOutput[field] = format(values[field]);
      rowOutput.net_cash_change = format(change);
      rowOutput.closing_cash_balance = format(balance);
      return rowOutput;
    });
    return { opening_cash: format(opening), ending_cash: format(balance),
      minimum_month_end_cash: format(minimum),
      additional_cash_needed_at_month_ends: format(cmp(minimum, ZERO) < 0 ? sub(ZERO, minimum) : ZERO),
      first_negative_month: firstNegative,
      net_operating_cashflow_before_other_uses: format(operatingTotal), months };
  }
  function evaluate(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Input must be an object');
    const currency = String(data.currency || '').trim().toUpperCase();
    if (!/^[A-Z0-9_]{1,12}$/.test(currency) || !/[A-Z0-9]/.test(currency)) {
      throw new Error('Currency must be a short code or clearly labeled unit');
    }
    if (!Array.isArray(data.enterprises) || data.enterprises.length < 1 || data.enterprises.length > LIMIT) {
      throw new Error('Enter 1 to 100 enterprises');
    }
    const names = new Set();
    const dataRows = data.enterprises.map((row) => {
      const item = enterprise(row);
      const lower = item.result.name.toLocaleLowerCase();
      if (names.has(lower)) throw new Error('Enterprise names must be unique');
      names.add(lower);
      return item;
    });
    const results = dataRows.map((x) => x.result);
    // Mirror the CLI accounting contract: aggregate the already-rounded line
    // items shown to a buyer, so detail reconciles exactly with the portfolio.
    const total = (field) => format(results.reduce((sum, x) =>
      add(sum, decimal(x[field], field, fraction(-(10n ** 70n)), fraction(10n ** 70n))), ZERO));
    const resources = {};
    for (const field of ['land_area_hectares', 'irrigation_water_m3']) {
      const key = field === 'land_area_hectares' ? 'land' : 'water';
      const observed = dataRows.filter((x) => x.numbers[key] !== null);
      const complete = observed.length === dataRows.length;
      resources[field] = { provided_enterprises: observed.length, complete_for_portfolio: complete,
        portfolio_total: complete ? exact(observed.reduce((sum, x) => add(sum, x.numbers[key]), ZERO)) : null };
    }
    const scenario = [];
    for (const x of dataRows) {
      for (const volume of ['0.80', '1.00', '1.20']) {
        for (const price of ['0.90', '1.00', '1.10']) {
          const n = x.numbers;
          const gross = mul(mul(n.price, decimal(price, 'factor')), sub(ONE, n.fee));
          const profit = sub(mul(mul(n.quantity, decimal(volume, 'factor')), sub(gross, n.variable)), n.fixed);
          scenario.push({ enterprise: x.result.name, volume_multiplier: volume,
            price_multiplier: price, modeled_operating_profit: format(profit) });
        }
      }
    }
    const report = { version: '2.0-browser', currency,
      accounting_scope: 'contribution_profit_before_depreciation_financing_tax',
      input_values_independently_validated: false,
      assumptions: [
        'All quantities, prices and costs are supplied by the user; no market feeds.',
        'Fixed costs are allocated per enterprise without double counting.',
        'This is scenario arithmetic, not a forecast or investment recommendation.',
        'Scenarios vary only units sold and price; fees and costs are held constant.',
        'Enterprise profit excludes tax, financing, capital expenditure, depreciation and working capital.',
        'Optional monthly cash flow is a separate user-entered cash timing plan.',
        'Resource intensity uses only reported values for the same accounting period.'
      ], results,
      portfolio: { sales_revenue: total('sales_revenue'), total_cost: total('total_cost'),
        operating_profit: total('operating_profit'), contribution_margin_total: total('contribution_margin_total') },
      resource_coverage: resources, scenario_results: scenario };
    if (Object.prototype.hasOwnProperty.call(data, 'cashflow_plan')) {
      report.cashflow = cashflowPlan(data.cashflow_plan);
    }
    return report;
  }
  const API = Object.freeze({ evaluate, enterprise, cashflowPlan, decimal, format });
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.FarmEconomics = API;
})(typeof globalThis === 'undefined' ? this : globalThis);

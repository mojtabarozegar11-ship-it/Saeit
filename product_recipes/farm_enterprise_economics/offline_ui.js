/* Accessible offline UI: no fetch, external dependency, tracking, cookies or storage. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const FIELDS = [
    ['name', 'Enterprise name', 'text', true],
    ['units_sold', 'Units sold in the period', 'decimal', true],
    ['unit_price', 'Selling price / unit', 'decimal', true],
    ['variable_cost_per_unit', 'Variable cost / unit', 'decimal', true],
    ['allocated_fixed_cost', 'Allocated fixed cost', 'decimal', true],
    ['selling_fee_percent', 'Selling fee (%)', 'decimal', false],
    ['land_area_hectares', 'Land area (hectares, optional)', 'decimal', false],
    ['irrigation_water_m3', 'Irrigation (m³, optional)', 'decimal', false]
  ];
  const SAMPLE = {
    name: 'Illustrative Orchard', units_sold: '1000', unit_price: '10',
    variable_cost_per_unit: '4', allocated_fixed_cost: '3000',
    selling_fee_percent: '5', land_area_hectares: '2.5', irrigation_water_m3: '500'
  };
  const CASH_FIELDS = [
    ['cash_receipts', 'Customer cash receipts'],
    ['operating_payments', 'Operating cash payments'],
    ['asset_purchases', 'Asset purchases'],
    ['loan_receipts', 'Loan cash received'],
    ['loan_repayments', 'Debt service'],
    ['other_payments', 'Other cash payments']
  ];
  let latest = null;
  let counter = 0;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  function field(key, label, type, required, value, uid) {
    const wrapper = element('label', label);
    const input = element('input');
    input.name = key;
    input.id = uid + '-' + key;
    input.value = value === undefined || value === null ? '' : String(value);
    input.required = required;
    input.autocomplete = 'off';
    if (type === 'decimal') {
      input.type = 'text'; input.inputMode = 'decimal'; input.maxLength = 64;
    } else { input.type = 'text'; input.maxLength = 120; }
    wrapper.append(input);
    return wrapper;
  }
  function addEnterprise(values = {}) {
    if ($('enterprise-list').children.length >= 100) throw new Error('Maximum 100 enterprises');
    const uid = 'crop-' + (++counter);
    const section = element('fieldset');
    section.className = 'enterprise';
    section.append(element('legend', 'Enterprise ' + $('enterprise-list').children.length.toString().padStart(2, '0')));
    const grid = element('div', null, 'fields');
    FIELDS.forEach(([key, label, type, required]) => grid.append(field(key, label, type, required, values[key], uid)));
    section.append(grid);
    const action = element('div', null, 'actions');
    const remove = element('button', 'Remove enterprise', 'danger');
    remove.type = 'button';
    remove.addEventListener('click', () => {
      if ($('enterprise-list').children.length <= 1) { showError('At least one enterprise is required'); return; }
      section.remove(); renumber(); invalidate();
    });
    action.append(remove); section.append(action);
    $('enterprise-list').append(section);
    invalidate();
  }
  function renumber() {
    [...$('enterprise-list').children].forEach((node, idx) => {
      node.querySelector('legend').textContent = 'Enterprise ' + String(idx + 1).padStart(2, '0');
    });
  }
  function invalidate() {
    latest = null;
    $('report').classList.add('hidden');
  }
  function zeroCashflow() {
    return { opening_cash: '0', months: Array.from({ length: 12 }, () =>
      Object.fromEntries(CASH_FIELDS.map(([name]) => [name, '0']))) };
  }
  function createCashflowRows() {
    const body = $('cash-month-inputs');
    for (let month = 1; month <= 12; month++) {
      const row = element('tr');
      row.append(element('th', String(month), 'cash-month'));
      for (const [name, label] of CASH_FIELDS) {
        const cell = element('td');
        const input = element('input');
        input.type = 'text'; input.inputMode = 'decimal'; input.maxLength = 64;
        input.className = 'cash-input'; input.name = name; input.value = '0';
        input.autocomplete = 'off'; input.required = true;
        input.setAttribute('aria-label', 'Month ' + month + ' ' + label);
        cell.append(input); row.append(cell);
      }
      body.append(row);
    }
  }
  function readCashflow() {
    const opening = $('cash-opening').value.trim();
    if (!opening) throw new Error('Opening cash balance is required');
    const months = [...$('cash-month-inputs').children].map((row, month) => {
      const record = {};
      for (const [field] of CASH_FIELDS) {
        const value = row.querySelector('[name="' + field + '"]').value.trim();
        if (!value) throw new Error('Month ' + (month + 1) + ' ' + field + ' is required');
        record[field] = value;
      }
      return record;
    });
    return { opening_cash: opening, months };
  }
  function fillCashflow(plan) {
    const source = plan || zeroCashflow();
    $('cash-opening').value = source.opening_cash;
    [...$('cash-month-inputs').children].forEach((row, month) => {
      for (const [field] of CASH_FIELDS) {
        row.querySelector('[name="' + field + '"]').value = source.months[month][field];
      }
    });
  }
  function readInput() {
    return { currency: $('currency').value.trim(), enterprises: [...$('enterprise-list').children].map((node) => {
      const row = {};
      for (const [key, , , required] of FIELDS) {
        const raw = node.querySelector('[name="' + key + '"]').value.trim();
        if (required && !raw) throw new Error(key + ': required field');
        if (raw !== '') row[key] = raw;
      }
      return row;
    }), cashflow_plan: readCashflow() };
  }
  function showError(message) {
    const box = $('feedback'); box.replaceChildren();
    box.append(element('p', message, 'error'));
  }
  function clearError() { $('feedback').replaceChildren(); }
  function tabulate(body, rows, keys) {
    body.replaceChildren();
    rows.forEach((row) => {
      const tr = element('tr');
      keys.forEach((key) => tr.append(element('td', row[key] === null || row[key] === undefined ? '—' : row[key])));
      body.append(tr);
    });
  }
  function render(report) {
    $('scope').textContent = 'Currency: ' + report.currency + '. Contribution accounting only; period and assumptions are yours.';
    $('portfolio').replaceChildren();
    [['sales_revenue', 'Revenue'], ['total_cost', 'Total modeled cost'],
      ['operating_profit', 'Operating profit (pre-tax etc.)'],
      ['contribution_margin_total', 'Contribution margin']].forEach(([key, label]) => {
      const cell = element('div', null, 'kpi');
      cell.append(element('span', label), element('strong', report.portfolio[key] + ' ' + report.currency));
      $('portfolio').append(cell);
    });
    tabulate($('results'), report.results, [
      'name', 'sales_revenue', 'operating_profit', 'break_even_units',
      'break_even_unit_price_at_planned_volume', 'margin_of_safety_percent'
    ]);
    const land = report.resource_coverage.land_area_hectares;
    const water = report.resource_coverage.irrigation_water_m3;
    $('coverage').textContent = 'Land recorded for ' + land.provided_enterprises + '/' + report.results.length +
      ' enterprises; irrigation recorded for ' + water.provided_enterprises + '/' + report.results.length +
      '. Missing usage is never assumed to equal zero. Per-resource profit is not marginal productivity.';
    tabulate($('resources'), report.results, [
      'name', 'land_area_hectares', 'operating_profit_per_hectare',
      'irrigation_water_m3', 'operating_profit_per_irrigation_m3'
    ]);
    tabulate($('scenarios'), report.scenario_results, [
      'enterprise', 'volume_multiplier', 'price_multiplier', 'modeled_operating_profit'
    ]);
    $('cash-summary').replaceChildren();
    const cash = report.cashflow;
    [['ending_cash', 'Closing cash after month 12'],
      ['minimum_month_end_cash', 'Lowest month-end cash'],
      ['additional_cash_needed_at_month_ends', 'Potential liquidity shortfall'],
      ['net_operating_cashflow_before_other_uses', 'Net cash from operating receipts/payments']]
      .forEach(([key, label]) => {
        const cell = element('div', null, 'kpi');
        cell.append(element('span', label), element('strong', cash[key] + ' ' + report.currency));
        $('cash-summary').append(cell);
      });
    const first = element('p', cash.first_negative_month === null
      ? 'No negative month-end balance in the entered plan.'
      : 'Warning: first negative month-end balance in month ' + cash.first_negative_month + '.',
    cash.first_negative_month === null ? 'success' : 'error');
    $('cash-summary').append(first);
    tabulate($('cash-results'), cash.months, ['month', 'net_cash_change', 'closing_cash_balance']);
    $('report').classList.remove('hidden');
  }
  function calculate() {
    try {
      const result = FarmEconomics.evaluate(readInput());
      latest = result; render(result); clearError();
    } catch (error) { invalidate(); showError(error.message); }
  }
  function download(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = element('a');
    anchor.href = url; anchor.download = filename;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function csvEscape(text) {
    // Every displayed CSV value has been validated or calculated; quote all fields.
    return '"' + String(text).replace(/"/g, '""') + '"';
  }
  function exportCSV() {
    if (!latest) { showError('Calculate before exporting'); return; }
    const columns = ['enterprise', 'volume_multiplier', 'price_multiplier', 'modeled_operating_profit'];
    const rows = [columns, ...latest.scenario_results.map((row) => columns.map((key) => row[key]))];
    download('farm_scenarios.csv', rows.map((row) => row.map(csvEscape).join(',')).join('\r\n') + '\r\n', 'text/csv;charset=utf-8');
  }
  function exportCashflowCSV() {
    if (!latest || !latest.cashflow) { showError('Calculate the 12-month cash plan before exporting'); return; }
    const columns = ['month', 'cash_receipts', 'operating_payments', 'asset_purchases',
      'loan_receipts', 'loan_repayments', 'other_payments', 'net_cash_change', 'closing_cash_balance'];
    const rows = [columns, ...latest.cashflow.months.map((row) => columns.map((key) => row[key]))];
    download('farm_cashflow_12_months.csv', rows.map((row) => row.map(csvEscape).join(',')).join('\r\n') + '\r\n', 'text/csv;charset=utf-8');
  }
  function fill(data) {
    // Validate BEFORE removing the user's current inputs. No partial imports.
    FarmEconomics.evaluate(data);
    const existing = $('enterprise-list');
    const prior = [...existing.children];
    const priorCash = readCashflow();
    try {
      existing.replaceChildren();
      data.enterprises.forEach((row) => addEnterprise(row));
      $('currency').value = data.currency;
      fillCashflow(data.cashflow_plan);
      renumber(); invalidate(); clearError();
    } catch (error) {
      existing.replaceChildren(...prior);
      fillCashflow(priorCash);
      throw error;
    }
  }
  $('add').addEventListener('click', () => {
    try { addEnterprise({ name: 'Enterprise ' + ($('enterprise-list').children.length + 1) }); renumber(); clearError(); }
    catch (error) { showError(error.message); }
  });
  $('calculate').addEventListener('click', calculate);
  $('enterprise-list').addEventListener('input', invalidate);
  $('currency').addEventListener('input', invalidate);
  $('cash-opening').addEventListener('input', invalidate);
  $('cash-month-inputs').addEventListener('input', invalidate);
  $('export-input').addEventListener('click', () => {
    try { const data = readInput(); FarmEconomics.evaluate(data);
      download('farm_inputs.json', JSON.stringify(data, null, 2) + '\n', 'application/json'); clearError();
    } catch (error) { showError(error.message); }
  });
  $('import').addEventListener('click', () => $('import-file').click());
  $('import-file').addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 150000) throw new Error('Input file exceeds 150 KB');
      fill(JSON.parse(await file.text()));
    } catch (error) { showError('Import rejected: ' + error.message); }
    finally { event.target.value = ''; }
  });
  $('export-report').addEventListener('click', () => {
    if (latest) download('farm_report.json', JSON.stringify(latest, null, 2) + '\n', 'application/json');
  });
  $('export-csv').addEventListener('click', exportCSV);
  $('export-cashflow-csv').addEventListener('click', exportCashflowCSV);
  $('print').addEventListener('click', () => { if (latest) window.print(); });
  createCashflowRows();
  addEnterprise(SAMPLE);
  calculate();
})();

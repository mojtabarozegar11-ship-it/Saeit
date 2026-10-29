/* Greenhouse Economics Studio — offline, deterministic economic model.
 * Copyright (c) 2026 Mojtaba Roozegar. All rights reserved.
 * Scope: user-entered scenarios, not agronomic or market forecasts.
 */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.GreenhouseEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  var VERSION = "3.0.0";

  function numeric(obj, key, min, max) {
    var raw = obj[key];
    if (raw === undefined || raw === null || String(raw).trim() === "") {
      throw new Error(key + " is required");
    }
    var value = Number(raw);
    if (!Number.isFinite(value) || value < min || value > max) {
      throw new Error(key + " must be between " + min + " and " + max);
    }
    return value;
  }
  function optionalNumeric(obj, key, min, max, fallback) {
    return obj[key] === undefined || obj[key] === null || String(obj[key]).trim() === ""
      ? fallback : numeric(obj, key, min, max);
  }
  function label(obj, key, maxLength) {
    var value = obj[key];
    if (typeof value !== "string" || !value.trim() || value.trim().length > maxLength ||
        /[\u0000-\u001F\u007F]/.test(value)) {
      throw new Error(key + " must be non-empty plain text (up to " + maxLength + " characters)");
    }
    return value.trim();
  }
  function normalized(source) {
    if (!source || typeof source !== "object" || Array.isArray(source)) {
      throw new Error("Scenario must be an object");
    }
    var p = {
      project: label(source, "project", 100),
      crop: label(source, "crop", 80),
      season: label(source, "season", 80),
      region: label(source, "region", 100),
      currency: label(source, "currency", 12).toUpperCase(),
      areaM2: numeric(source, "areaM2", 0.001, 100000000),
      yieldKgM2: numeric(source, "yieldKgM2", 0, 100000),
      rejectionPct: numeric(source, "rejectionPct", 0, 100),
      priceKg: numeric(source, "priceKg", 0, 100000000),
      cyclesYear: numeric(source, "cyclesYear", 1, 12),
      years: numeric(source, "years", 1, 30),
      initialInvestment: numeric(source, "initialInvestment", 0, 1e12),
      fixedAnnual: numeric(source, "fixedAnnual", 0, 1e12),
      waterLitersM2: numeric(source, "waterLitersM2", 0, 1e8),
      waterPriceLiter: numeric(source, "waterPriceLiter", 0, 1e8),
      energyKwhM2: numeric(source, "energyKwhM2", 0, 1e8),
      energyPriceKwh: numeric(source, "energyPriceKwh", 0, 1e8),
      climateKwhM2: numeric(source, "climateKwhM2", 0, 1e8),
      climatePriceKwh: numeric(source, "climatePriceKwh", 0, 1e8),
      laborHoursM2: numeric(source, "laborHoursM2", 0, 1e8),
      laborPriceHour: numeric(source, "laborPriceHour", 0, 1e8),
      otherVariableM2: numeric(source, "otherVariableM2", 0, 1e8),
      packagingKg: numeric(source, "packagingKg", 0, 1e8),
      logisticsKg: numeric(source, "logisticsKg", 0, 1e8),
      discountPct: numeric(source, "discountPct", 0, 100),
      revenueGrowthPct: numeric(source, "revenueGrowthPct", -50, 50),
      costGrowthPct: numeric(source, "costGrowthPct", -50, 50)
    };
    if (!/^[A-Z0-9_]{1,12}$/.test(p.currency)) throw new Error("currency must be a short ASCII unit code");
    if (!Number.isInteger(p.cyclesYear) || !Number.isInteger(p.years))
      throw new Error("cyclesYear and years must be whole numbers");
    var keys = ["yieldMin", "yieldMax", "priceMin", "priceMax"];
    var supplied = keys.filter(function (key) {
      return source[key] !== undefined && source[key] !== null && String(source[key]).trim() !== "";
    });
    if (supplied.length !== 0 && supplied.length !== 4)
      throw new Error("Risk analysis needs all four minimum/maximum fields");
    if (supplied.length === 4) {
      keys.forEach(function (key) { p[key] = numeric(source, key, 0, 1e8); });
      if (!(p.yieldMin <= p.yieldKgM2 && p.yieldKgM2 <= p.yieldMax &&
            p.priceMin <= p.priceKg && p.priceKg <= p.priceMax)) {
        throw new Error("Risk bounds must contain expected yield and selling price");
      }
      p.riskSeed = optionalNumeric(source, "riskSeed", 0, 2147483647, 20261029);
      if (!Number.isInteger(p.riskSeed)) throw new Error("riskSeed must be a whole number");
    }
    return p;
  }
  function resourceCosts(p) {
    return {
      water: p.areaM2 * p.waterLitersM2 * p.waterPriceLiter,
      energy: p.areaM2 * p.energyKwhM2 * p.energyPriceKwh,
      climate: p.areaM2 * p.climateKwhM2 * p.climatePriceKwh,
      labor: p.areaM2 * p.laborHoursM2 * p.laborPriceHour,
      other: p.areaM2 * p.otherVariableM2
    };
  }
  function evaluatedCycle(p, yieldRate, price) {
    var grossKg = p.areaM2 * yieldRate;
    var saleableKg = grossKg * (1 - p.rejectionPct / 100);
    var breakdown = resourceCosts(p);
    breakdown.packaging = saleableKg * p.packagingKg;
    breakdown.logistics = saleableKg * p.logisticsKg;
    var variableCost = Object.keys(breakdown).reduce(function (sum, k) { return sum + breakdown[k]; }, 0);
    var revenue = saleableKg * price;
    return {
      grossKg: grossKg, saleableKg: saleableKg, revenue: revenue,
      variableCost: variableCost, breakdown: breakdown,
      contribution: revenue - variableCost,
      allocatedFixedCost: p.fixedAnnual / p.cyclesYear,
      cycleMargin: revenue - variableCost - p.fixedAnnual / p.cyclesYear
    };
  }
  function annualSchedule(p, cycle) {
    var rows = [], npv = -p.initialInvestment, cumulative = -p.initialInvestment;
    var payback = p.initialInvestment === 0 ? 0 : null;
    var sumNet = 0;
    for (var i = 0; i < p.years; i++) {
      var revenue = p.cyclesYear * cycle.revenue * Math.pow(1 + p.revenueGrowthPct / 100, i);
      var variable = p.cyclesYear * cycle.variableCost * Math.pow(1 + p.costGrowthPct / 100, i);
      var fixed = p.fixedAnnual * Math.pow(1 + p.costGrowthPct / 100, i);
      var net = revenue - variable - fixed;
      var before = cumulative;
      cumulative += net;
      sumNet += net;
      npv += net / Math.pow(1 + p.discountPct / 100, i + 1);
      if (payback === null && net > 0 && before < 0 && cumulative >= 0) {
        payback = i + (-before / net);
      }
      rows.push({ year: i + 1, revenue: revenue, variableCost: variable,
        fixedCost: fixed, netCashFlow: net, cumulativeCashFlow: cumulative });
    }
    return {
      years: rows, npv: npv, paybackYears: payback,
      totalOperatingCashFlow: sumNet,
      roiPct: p.initialInvestment > 0 ? (sumNet - p.initialInvestment) / p.initialInvestment * 100 : null
    };
  }
  function threshold(p, cycle) {
    var saleableKg = cycle.saleableKg;
    var breakEvenPrice = saleableKg > 0 ?
      (cycle.variableCost + p.fixedAnnual / p.cyclesYear) / saleableKg : null;
    var unitServiceCost = p.packagingKg + p.logisticsKg;
    var resource = Object.keys(cycle.breakdown).filter(function (k) {
      return k !== "packaging" && k !== "logistics";
    }).reduce(function (total, key) { return total + cycle.breakdown[key]; }, 0);
    var requiredBase = resource + p.fixedAnnual / p.cyclesYear;
    var unitContribution = p.priceKg - unitServiceCost;
    var factor = p.areaM2 * (1 - p.rejectionPct / 100) * unitContribution;
    var breakEvenYield = requiredBase === 0 ? 0 : factor > 0 ? requiredBase / factor : null;
    return {
      pricePerKg: breakEvenPrice === null ? null : Math.ceil(breakEvenPrice * 100) / 100,
      grossYieldKgM2: breakEvenYield === null ? null : Math.ceil(breakEvenYield * 1000) / 1000,
      limitation: "Break-even thresholds assume unchanged crop, rejected fraction, entered resource costs and per-kg service costs."
    };
  }
  function stressCases(p) {
    var rows = [];
    [-0.20, 0, 0.20].forEach(function (y) {
      [-0.10, 0, 0.10].forEach(function (priceDelta) {
        var value = evaluatedCycle(p, p.yieldKgM2 * (1 + y), p.priceKg * (1 + priceDelta));
        rows.push({ yieldChangePct: y * 100, priceChangePct: priceDelta * 100,
          annualNet: p.cyclesYear * value.contribution - p.fixedAnnual,
          cycleMargin: value.cycleMargin });
      });
    });
    return rows;
  }
  function seeded(seed) {
    var state = seed >>> 0;
    return function () {
      state += 0x6D2B79F5;
      var v = state;
      v = Math.imul(v ^ (v >>> 15), v | 1);
      v ^= v + Math.imul(v ^ (v >>> 7), v | 61);
      return ((v ^ (v >>> 14)) >>> 0) / 4294967296;
    };
  }
  function triangular(rng, min, mode, max) {
    if (max === min) return min;
    var u = rng(), split = (mode - min) / (max - min);
    return u < split ? min + Math.sqrt(u * (max - min) * (mode - min)) :
      max - Math.sqrt((1 - u) * (max - min) * (max - mode));
  }
  function risk(p) {
    if (p.yieldMin === undefined) return null;
    var rng = seeded(p.riskSeed), values = [], countLosses = 0;
    for (var i = 0; i < 2000; i++) {
      var simulated = evaluatedCycle(
        p, triangular(rng, p.yieldMin, p.yieldKgM2, p.yieldMax),
        triangular(rng, p.priceMin, p.priceKg, p.priceMax));
      var annual = p.cyclesYear * simulated.contribution - p.fixedAnnual;
      if (annual < 0) countLosses++;
      values.push(annual);
    }
    values.sort(function (a, b) { return a - b; });
    return {
      simulations: values.length, annualLossFrequencyPct: 100 * countLosses / values.length,
      p05: values[99], median: values[999], p95: values[1899], seed: p.riskSeed,
      method: "Independent user-defined triangular yield and price distributions; uncalibrated illustration, NOT a market probability."
    };
  }
  function calculate(source) {
    var p = normalized(source);
    var cycle = evaluatedCycle(p, p.yieldKgM2, p.priceKg);
    var annual = annualSchedule(p, cycle);
    return {
      version: VERSION, inputs: p, cycle: cycle,
      yearOne: annual.years[0], financials: annual,
      breakEven: threshold(p, cycle), stress: stressCases(p), risk: risk(p),
      scope: "Offline, user-supplied scenarios only. Excludes taxes, financing, depreciation, residual value, working capital, crop-specific agronomy and expenses not entered. No market data or professional advice."
    };
  }
  return { version: VERSION, calculate: calculate, normalized: normalized,
    evaluatedCycle: evaluatedCycle, triangular: triangular };
});

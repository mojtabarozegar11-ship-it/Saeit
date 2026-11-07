#!/usr/bin/env node
/**
 * Read-only browser acceptance gate for the ORIGINAL Living Cities world.
 *
 * Runs in a clean browser context, performs navigation only, and never buys,
 * *builds*, modifies a save, or deploys anything. Its default target is the
 * existing MojPlayWin edition, not the unrelated Bazei MojCoin facade.
 *
 * Usage: node scripts/living_cities_canvas_gate.mjs
 *        node scripts/living_cities_canvas_gate.mjs --url https://zomorodmelal.ir/living-cities/play/
 *        node scripts/living_cities_canvas_gate.mjs --compare
 */

import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const TARGETS = new Set([
  'https://mojplaywin.com/living-cities/play/',
  'https://zomorodmelal.ir/living-cities/play/',
]);

export function evaluateSceneSnapshot(snapshot) {
  const issues = [];
  if (!snapshot || typeof snapshot !== 'object') return ['missing_scene_snapshot'];
  if (!snapshot.hasOriginalGameTitle) issues.push('original_living_cities_missing');
  if (!snapshot.hasBuildTab) issues.push('build_tab_missing');
  if (!snapshot.hasWorldCanvas) issues.push('world_canvas_missing');
  else {
    if (snapshot.display === 'none' || snapshot.visibility === 'hidden')
      issues.push('world_canvas_hidden');
    if (!(snapshot.width >= 320 && snapshot.height >= 240))
      issues.push('world_canvas_zero_or_too_small');
  }
  return issues;
}

/** Diagnostic differences only: localization/branding may be intentional. */
export function compareEditionSnapshots(left, right) {
  const differences = [];
  for (const field of ['languageOptions', 'hasWorldTour', 'hasJourney', 'hasQuests']) {
    if (left[field] !== right[field]) differences.push({ field, left: left[field], right: right[field] });
  }
  return differences;
}

export async function inspectOriginalWorld(page, target) {
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.getByRole('tab', { name: /Build/i }).click({ timeout: 10000 });
  // Wait for normal scene initialization; do not mutate app state or click a plot.
  await page.waitForTimeout(2000);
  return page.evaluate(() => {
    const canvas = document.querySelector('#world');
    const rect = canvas?.getBoundingClientRect();
    const css = canvas ? getComputedStyle(canvas) : null;
    return {
      hasOriginalGameTitle: Boolean(document.querySelector('h1')?.textContent?.includes('LIVING CITIES')),
      hasBuildTab: Boolean(document.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.includes('Build')),
      hasWorldCanvas: Boolean(canvas),
      display: css?.display ?? null,
      visibility: css?.visibility ?? null,
      width: rect?.width ?? 0,
      height: rect?.height ?? 0,
      inlineStyle: canvas?.getAttribute('style') ?? null,
      documentTitle: document.title,
      languageOptions: document.querySelectorAll('#lcLanguage option').length,
      hasWorldTour: [...document.querySelectorAll('[role="tab"]')].some((tab) => tab.textContent?.includes('World Tour')),
      hasJourney: [...document.querySelectorAll('[role="tab"]')].some((tab) => tab.textContent?.includes('Journey')),
      hasQuests: [...document.querySelectorAll('[role="tab"]')].some((tab) => /quests/i.test(tab.textContent ?? '')),
    };
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 0 && !(args.length === 1 && args[0] === '--compare') &&
      !(args.length === 2 && args[0] === '--url')) {
    throw new Error('usage: node scripts/living_cities_canvas_gate.mjs [--url APPROVED_URL | --compare]');
  }
  const selected = args[0] === '--compare' ? [...TARGETS] :
    [args.length ? args[1] : 'https://mojplaywin.com/living-cities/play/'];
  if (!selected.every((target) => TARGETS.has(target))) throw new Error('unapproved_game_origin');
  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  try {
    const reports = [];
    for (const target of selected) {
      // Separate ephemeral context; never read or rewrite a player's stored save.
      const context = await browser.newContext({ viewport: { width: 1365, height: 920 }, reducedMotion: 'reduce' });
      try {
        const page = await context.newPage();
        const exceptions = [];
        page.on('pageerror', (error) => exceptions.push(String(error).slice(0, 500)));
        const snapshot = await inspectOriginalWorld(page, target);
        const issues = evaluateSceneSnapshot(snapshot);
        reports.push({ target, snapshot, issues, pageErrors: exceptions });
        if (issues.length || exceptions.length) process.exitCode = 1;
      } finally {
        await context.close();
      }
    }
    const differences = reports.length === 2 ?
      compareEditionSnapshots(reports[0].snapshot, reports[1].snapshot) : [];
    console.log(JSON.stringify({ reports, observedEditionDifferences: differences,
      note: 'Feature differences need a release decision; titles/localization are not assumed identical.' }, null, 2));
    if (differences.length) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => { console.error(`LIVING_CITIES_CANVAS_GATE=ERROR ${error.message}`); process.exitCode = 2; });
}

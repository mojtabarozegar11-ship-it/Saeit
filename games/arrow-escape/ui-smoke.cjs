/* Browser QA: tap each solution path, win, advance and exercise restore/help. */
'use strict';
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath(), args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto('file://' + path.resolve(__dirname, 'index.html'), { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.ArrowMazeDebug));
    const initial = await page.evaluate(() => window.ArrowMazeDebug.getState());
    assert.equal(initial.level, 1);
    assert.ok(initial.remaining >= 6);
    async function tapPiece(id) {
      const target = await page.evaluate(pieceId => {
        const puzzle = window.ArrowMazeDebug.getPuzzle();
        const piece = puzzle.pieces.find(entry => entry.id === pieceId);
        const canvas = document.getElementById('gameBoard');
        const rect = canvas.getBoundingClientRect();
        const size = puzzle.size;
        const margin = canvas.width * .065;
        const cell = (canvas.width - margin * 2) / size;
        const first = piece.path[0];
        return {
          x: rect.left + (margin + (first.x + .5) * cell) * rect.width / canvas.width,
          y: rect.top + (margin + (first.y + .5) * cell) * rect.height / canvas.height
        };
      }, id);
      await page.mouse.click(target.x, target.y);
    }
    const puzzle = await page.evaluate(() => window.ArrowMazeDebug.getPuzzle());
    for (const id of puzzle.solution) {
      const before = await page.evaluate(() => window.ArrowMazeDebug.getState().remaining);
      await tapPiece(id);
      await page.waitForFunction(old => window.ArrowMazeDebug.getState().remaining < old, before);
    }
    await page.locator('#overlayAction').waitFor({ state: 'visible' });
    assert.equal((await page.evaluate(() => window.ArrowMazeDebug.getState())).remaining, 0);
    await page.locator('#overlayAction').click();
    const stageTwo = await page.evaluate(() => window.ArrowMazeDebug.getState());
    assert.equal(stageTwo.level, 2);
    assert.equal(stageTwo.hearts, 5);
    await page.locator('#hintButton').click();
    assert.match(await page.locator('#statusText').textContent(), /سبز/);
    await page.locator('#soundButton').click();
    assert.equal(await page.locator('#soundButton').getAttribute('aria-pressed'), 'false');
    await page.locator('#restartButton').click();
    assert.equal((await page.evaluate(() => window.ArrowMazeDebug.getState())).remaining, stageTwo.total);
    await page.reload();
    await page.waitForFunction(() => Boolean(window.ArrowMazeDebug));
    assert.equal((await page.evaluate(() => window.ArrowMazeDebug.getState())).level, 2);
    assert.deepEqual(errors, []);
    console.log('ARROW_MOBILE_BROWSER_QA=PASS', { completedLevel: 1, restoredLevel: 2, initial });
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

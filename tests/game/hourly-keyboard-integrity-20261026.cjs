'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const read = path => fs.readFileSync(path, 'utf8');
function sourceFunction(source, name) {
  const start = source.indexOf('function ' + name + '(');
  assert(start >= 0, name + ' missing');
  const opening = source.indexOf('{', start);
  let depth = 0;
  for (let i = opening; i < source.length; i++) {
    if (source[i] === '{') depth++;
    if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error('Unbalanced ' + name);
}
function functionUnderTest(path, name, context = {}) {
  return vm.runInNewContext(sourceFunction(read(path), name) + '; ' + name, context, {timeout: 1000});
}
const base = 'site_releases/mojplaywin/games-20261021/';
for (const slug of ['beacon-labyrinth', 'cipher-garden', 'nebula-salvage']) {
  const keyboard = functionUnderTest(base + slug + '/index.html', 'acceptsGameKeyboard', {running: true});
  assert.equal(keyboard({target: {tagName: 'CANVAS'}}), true, slug + ' canvas');
  for (const tagName of ['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'A']) {
    assert.equal(keyboard({target: {tagName}}), false, slug + ' should preserve ' + tagName);
  }
  for (const flag of ['ctrlKey', 'altKey', 'metaKey', 'isComposing']) {
    assert.equal(keyboard({target: {tagName: 'CANVAS'}, [flag]: true}), false, slug + ' ' + flag);
  }
  assert.equal(keyboard({target: {isContentEditable: true}}), false);
  const source = read(base + slug + '/index.html');
  assert(source.includes("window.addEventListener('blur',()=>{keys.clear()"));
  assert(source.includes("if(document.hidden){keys.clear()"));
  console.log('PASS ' + slug + ': native controls, modifiers, blur and visibility');
}
for (const path of ['games/air-supremacy/index.html', 'games/air-supremacy-fa/index.html']) {
  const keyboard = functionUnderTest(path, 'acceptsFlightKey', {run: true, paused: false});
  assert.equal(keyboard({target: {tagName: 'CANVAS'}}), true);
  assert.equal(keyboard({target: {tagName: 'BUTTON'}}), false);
  assert.equal(keyboard({target: {tagName: 'INPUT'}}), false);
  assert.equal(keyboard({target: {tagName: 'CANVAS'}, metaKey: true}), false);
  assert.equal(keyboard({target: {tagName: 'CANVAS'}, isComposing: true}), false);
  assert.equal(functionUnderTest(path, 'acceptsFlightKey', {run: true, paused: true})({target: {tagName: 'CANVAS'}}), false);
  console.log('PASS ' + path + ': flight input isolation');
}
const bounded = functionUnderTest('games/crown-defender/index.html', 'boundedSaveNumber');
assert.equal(bounded(Infinity, 0, 1000000), 0);
assert.equal(bounded(-10, 0, 1000000), 0);
assert.equal(bounded('123.9', 0, 1000000), 123);
assert.equal(bounded(100000000, 0, 1000000), 1000000);
assert.equal(bounded(NaN, 1, 10), 1);
console.log('PASS Crown Defender: bounded finite save fields');
const validatedHero = functionUnderTest('games/ramadan-war/game.js', 'validatedHero', {NAMES: Array(30)});
for (const invalid of [-1, 30, Infinity, NaN, 'nope', 1.5]) assert.equal(validatedHero(invalid), 0);
assert.equal(validatedHero('29'), 29);
console.log('PASS Ramadan War: corrupted hero preference');
{
  const messages = [], score = {textContent: ''};
  const overlay = {classList: {contains: () => true}};
  const stage = {tabIndex: -1, listeners: {}, append() {}, addEventListener(event, fn) {this.listeners[event] = fn;}};
  const context = {
    document: {createElement: () => ({style: {}, textContent: ''})},
    button(text, callback) {return {textContent: text, style: {}, click() {if (this.onclick) this.onclick(); else callback();}};},
    $: selector => selector === '#runScore' ? score : overlay,
    message: (_, msg) => messages.push(msg),
    showToast() {},
  };
  functionUnderTest('templates/studio_raha/index.html', 'runnerGame', context)(stage);
  assert.equal(stage.tabIndex, 0);
  assert.equal(typeof stage.listeners.keydown, 'function');
  for (let i = 0; i < 8; i++) stage.listeners.keydown({code: 'Space', target: stage, preventDefault() {}});
  assert.equal(score.textContent, 'Score: 8 / 8');
  assert(messages.some(m => m.includes('finish')));
  assert(!('keydown' in context.document));
  console.log('PASS Super Jungle Run: eight reliable keyboard jumps without global listener');
}
{
  const preview = {textContent: '', style: {}};
  const icing = {oninput: null};
  const toppings = [{dataset: {top: '🍓'}}, {dataset: {top: '🌼'}}];
  const candle = {onclick: null};
  const gamebody = {querySelectorAll: () => toppings, querySelector: selector => selector.includes('candle') ? candle : null};
  const context = {
    gamebody,
    stage() {},
    btn: (label, action) => '<button data-action="' + action + '">' + label + '</button>',
    $: selector => selector === '#icing' ? icing : preview,
    say() {},
  };
  functionUnderTest('templates/taniya_studio/index.html', 'mountCake', context)();
  for (let i = 0; i < 13; i++) candle.onclick({stopPropagation() {}});
  assert.equal((preview.textContent.match(/🕯️/g) || []).length, 12);
  toppings[1].onclick();
  assert(preview.textContent.includes('🌼'));
  assert.equal((preview.textContent.match(/🕯️/g) || []).length, 12);
  icing.oninput({target: {value: '#abcdef'}});
  assert(preview.style.filter.includes('#abcdef'));
  console.log('PASS Cake Maker: bounded candles survive decoration changes');
}
console.log('PASS all nine independently modified game files');

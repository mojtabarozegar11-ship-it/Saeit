import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';

class Element {
  constructor(tag = 'div', registry) {
    this.tag = tag;
    this.registry = registry;
    this.children = [];
    this.attributes = new Map();
    this.style = {};
    this.handlers = new Map();
    this.id = '';
  }
  setAttribute(key, value) { this.attributes.set(key, value); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(key, handler) { this.handlers.set(key, handler); }
  click() { this.handlers.get('click')?.(); }
  insertAdjacentElement(_position, node) { this.registry.set(node.id, node); }
  remove() { this.registry.delete(this.id); }
}

function buildHarness() {
  const source = spawnSync('python', ['-c',
    'from scripts.living_cities_webgl_fallback_patch import FALLBACK; print(FALLBACK)'],
    { encoding: 'utf8' });
  assert.equal(source.status, 0, source.stderr);
  const registry = new Map();
  const world = new Element('canvas', registry);
  world.id = 'world';
  registry.set(world.id, world);
  const city = { seed: 1, biome: 'MEADOW', buildings: [{ x: 1, z: 1, type: 'farm' }] };
  const context = {
    document: {
      getElementById: (id) => registry.get(id) || null,
      createElement: (tag) => new Element(tag, registry),
    },
    $: (selector) => registry.get(selector.slice(1)),
    game: {},
    cityById: () => city,
    BUILDINGS: { farm: { name: 'Sunfarm', icon: '🌾' } },
    terrain: () => 'plain',
    isBuildable: (_city, x, z) => !(x === 1 && z === 1),
    selection: { x: 2, z: 3 },
    renderer: undefined,
    tab: 'build',
    updatePanelCount: 0,
    updatePanel() { this.updatePanelCount++; },
    setTab() { throw Error('Unexpected tab change'); },
  };
  context.updatePanel = () => { context.updatePanelCount++; };
  vm.createContext(context);
  vm.runInContext(source.stdout, context);
  return { context, registry, world };
}

test('WebGL-disabled original city presents 81 keyboard-accessible actionable tiles', () => {
  const { context, registry, world } = buildHarness();
  context.renderFallbackWorld();
  const fallback = registry.get('worldFallback');
  assert.ok(fallback);
  assert.equal(fallback.getAttribute('role'), 'region');
  assert.equal(world.style.display, 'none');
  const grid = fallback.children[1];
  assert.equal(grid.children.length, 81);
  assert.match(grid.children[10].getAttribute('aria-label'), /Sunfarm/);
  assert.equal(grid.children[29].getAttribute('aria-pressed'), 'true');
  assert.equal(grid.children[4].tag, 'button');
  assert.equal(grid.children[4].type, 'button');
  grid.children[4].click();
  assert.equal(context.selection.x, 4);
  assert.equal(context.selection.z, 0);
  assert.equal(context.updatePanelCount, 1);
  assert.equal(fallback.children[1].children[4].getAttribute('aria-pressed'), 'true');
});

test('restoring the real original renderer removes fallback and makes canvas visible', () => {
  const { context, registry, world } = buildHarness();
  context.renderFallbackWorld();
  context.renderer = { draw() {} };
  context.renderFallbackWorld();
  assert.equal(registry.has('worldFallback'), false);
  assert.equal(world.style.display, '');
});

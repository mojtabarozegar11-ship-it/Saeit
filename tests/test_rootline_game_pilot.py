"""Acceptance tests for ROOTLINE: Bloom Defense (F14 private game pilot)."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "product_recipes/rootline_bloom_defense"


class RootlineGameTests(unittest.TestCase):
    def test_complete_local_package_and_no_external_dependencies(self):
        page = (GAME / "index.html").read_text(encoding="utf-8")
        script = (GAME / "game.js").read_text(encoding="utf-8")
        engine = (GAME / "engine.js").read_text(encoding="utf-8")
        css = (GAME / "game.css").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", page.lower())
        self.assertLess(page.index('src="engine.js"'), page.index('src="game.js"'))
        for name in ("field", "overlay", "wave", "health", "water", "score", "best",
                     "rain", "pause", "restart", "launch", "mute", "notice"):
            self.assertIn('id="' + name + '"', page)
        for label in ('data-kind="thorn"', 'data-kind="mist"', 'data-kind="well"'):
            self.assertIn(label, page)
        self.assertIn("touch-action:manipulation", css)
        self.assertIn("pointerdown", script)
        self.assertIn("keydown", script)
        self.assertIn("aria-live", page)
        for text in (page, script, engine, css):
            self.assertNotIn("https://", text)
            self.assertNotIn("http://", text)
            self.assertNotIn("fetch(", text)
            self.assertNotIn("XMLHttpRequest", text)
        self.assertIn("no purchases, advertising, login, trackers or external assets", page)

    def test_engine_logic_on_real_node_runtime(self):
        if not shutil.which("node"):
            self.skipTest("Node.js not present")
        for f in ("engine.js", "game.js"):
            check = subprocess.run(["node", "--check", str(GAME / f)],
                                   capture_output=True, text=True, timeout=15)
            self.assertEqual(check.returncode, 0, check.stderr[-1200:])
        js = r"""
'use strict';
const assert=require('node:assert/strict');
const E=require(process.argv[1]);
let g=E.newGame();
assert.equal(E.ROWS,5);assert.equal(E.COLS,8);assert.equal(g.water,38);
assert.equal(E.plant(g,0,0,'thorn').ok,false);
assert.equal(E.start(g),true);
assert.equal(g.wave,1);
assert.equal(E.plant(g,0,0,'thorn').ok,true);
assert.equal(g.water,26);
assert.equal(E.plant(g,0,0,'thorn').ok,false);
assert.equal(E.plant(g,-1,0,'thorn').ok,false);
assert.equal(E.plant(g,0,8,'thorn').ok,false);
assert.equal(E.plant(g,0,1,'wrong').ok,false);
assert.equal(E.choose(g,'mist'),true);
assert.equal(E.choose(g,'invalid'),false);
const oldElapsed=g.elapsed;
g.paused=true;E.advance(g,.1);
assert.equal(g.elapsed,oldElapsed);
g.paused=false;E.advance(g,.1);
assert(g.elapsed>oldElapsed);
g=E.newGame();E.start(g);g.water=100;
assert.equal(E.plant(g,0,0,'thorn').ok,true);
g.enemies=[{id:8,row:0,x:165,hp:12,maxHp:12,speed:0,points:17,hurt:1,slow:0,phase:0}];
for(let step=0;step<3;step++)E.advance(g,.1);
assert.equal(g.enemies.length,0);assert.equal(g.score,17);
g=E.newGame();E.start(g);g.water=100;
g.enemies=[{id:9,row:1,x:500,hp:40,maxHp:40,speed:10,points:15,hurt:1,slow:0,phase:0}];
assert.equal(E.rainburst(g).ok,true);
assert.equal(g.water,75);assert(g.enemies[0].hp<40);
assert.equal(E.rainburst(g).ok,false);
g=E.newGame();E.start(g);g.health=1;
g.enemies=[{id:10,row:3,x:68.2,hp:40,maxHp:40,speed:20,points:15,hurt:1,slow:0,phase:0}];
E.advance(g,.1);assert.equal(g.health,0);assert.equal(g.over,true);
const frozen=g.elapsed;E.advance(g,4);assert.equal(g.elapsed,frozen);
g=E.newGame();E.start(g);
for(let i=0;i<55;i++)E.advance(g,.1);
assert(g.enemies.length>0||g.health<12);
assert.equal(g.waveRemaining<5,true);
console.log('ROOTLINE_REAL_ENGINE_ACCEPTANCE=PASS');
"""
        run = subprocess.run(["node", "-e", js, str(GAME / "engine.js")],
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr[-1800:])
        self.assertIn("ROOTLINE_REAL_ENGINE_ACCEPTANCE=PASS", run.stdout)

    def test_release_gates_remain_closed(self):
        readme = (GAME / "COMMERCIAL_PILOT.md").read_text(encoding="utf-8")
        for gate in ("manual playtesting", "independent specialist",
                     "rights and provenance", "real device", "merchant", "NOT FOR LIVE SALE"):
            self.assertIn(gate, readme)
        self.assertNotIn("public checkout enabled", readme.lower())


if __name__ == "__main__":
    unittest.main()

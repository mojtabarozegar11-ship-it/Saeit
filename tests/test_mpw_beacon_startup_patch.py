"""Fail-closed regression tests for the sole Beacon Labyrinth live HTML patch."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "site_patches/mojplaywin/20261021/beacon-labyrinth/index.html"
CONTROL = ROOT / "scripts/patch_mpw_beacon_beta.py"

NODE_RUNTIME = r"""
const vm = require('vm');
const fs = require('fs');
const src = fs.readFileSync(0,'utf8');
const elements = {}, events = {};
let frame;
const gradient = {addColorStop(){}};
const canvasCtx = new Proxy({}, {get(o,p) {
  if (p in o) return o[p];
  if (p === 'createLinearGradient' || p === 'createRadialGradient') return () => gradient;
  return () => {};
}, set(o,p,v){o[p]=v;return true;}});
const node = id => elements[id] ??= {
  id, hidden:false, textContent:'', dataset:{}, handlers:{},
  addEventListener(type,handler){this.handlers[type]=handler},
  getContext(){return canvasCtx},
  getBoundingClientRect(){return {left:0,top:0,width:960,height:600}},
  focus(){}
};
const document = {getElementById:node,querySelectorAll:()=>[],
  addEventListener(type,cb){events[type]=cb},hidden:false};
const window = {addEventListener(){}};
vm.runInNewContext(src,{document,window,requestAnimationFrame:f=>frame=f,
  localStorage:{getItem:()=>null,setItem:()=>{}},console},{timeout:3000});
frame(16); frame(32); // critical: draw before player clicks Start
node('playButton').handlers.click();
for (let i=3;i<140;i++) frame(i*16.667);
if(node('overlay').hidden!==true) throw new Error('START_CONTROL_FAILED');
if(node('level').textContent!=='1 / 5') throw new Error('MAZE_NOT_INITIALIZED');
if(!String(node('state').textContent).includes('LIVES')) throw new Error('GAME_HUD_MISSING');
console.log('BEACON_INITIAL_FRAME_AND_START_SMOKE_PASS');
"""

class TestBeaconScopedPatch(unittest.TestCase):
    def test_scope_and_expected_baseline(self):
        source = CONTROL.read_text(encoding="utf-8")
        self.assertIn('0f2e7840def2e558b526ee70a9465f2f80b857b6', source)
        self.assertIn('mojplaywin-five-games-v2', source)
        self.assertIn('os.replace(temp, DEST)', source)
        self.assertIn('blob_sha(DEST.read_bytes())', source)
        self.assertNotIn('subprocess', source)
        self.assertNotIn('passenger_wsgi.py").write', source)

    def test_html_metadata_and_guard(self):
        s = PATCH.read_text(encoding="utf-8")
        for token in ('<html lang="en">','name="viewport"','role="status"',
                      'if(!maze.length){a.fillBg(200);return}',
                      'beacon-initial-frame-fix-20261021',
                      'not a Google Play release', 'localStorage',
                      'https://mojplaywin.com/game-releases/20261021/beacon-labyrinth/index.html'):
            self.assertIn(token,s)
        self.assertEqual(s.count('beacon-initial-frame-fix-20261021'),1)
        self.assertEqual(len(re.findall(r'<script>(.*?)</script>',s,re.S)),1)
        for token in ('fetch(', 'XMLHttpRequest', '<script src=', 'eval('):
            self.assertNotIn(token,s)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_pre_start_canvas_and_game_start(self):
        s = PATCH.read_text(encoding="utf-8")
        js = re.search(r'<script>(.*?)</script>',s,re.S).group(1)
        proc = subprocess.run(['node','-e', NODE_RUNTIME],input=js,text=True,
                              capture_output=True,timeout=15,check=False)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertIn('BEACON_INITIAL_FRAME_AND_START_SMOKE_PASS',proc.stdout)

if __name__ == '__main__':
    unittest.main()

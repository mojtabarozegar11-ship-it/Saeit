#!/usr/bin/env python3
"""Prepare a source-preserving WebGL fallback for the ORIGINAL Living Cities app.

Reads one verified app.mjs source and emits a patched candidate to stdout.
Never edits a source file, uses the deployment relay, or touches live player data.
Use ``--expected-sha256`` to pin the exact release being examined.
"""

import argparse
import hashlib
from pathlib import Path
import sys


FALLBACK = r'''
// WebGL-unavailable fallback for the ORIGINAL world: same state and build actions.
function renderFallbackWorld(){
  const canvas=$("#world"),existing=$("#worldFallback");
  if(renderer){existing?.remove();canvas.style.display="";return;}
  canvas.style.display="none";
  const panel=existing||document.createElement("section");
  if(!existing){
    panel.id="worldFallback";panel.setAttribute("role","region");
    panel.setAttribute("aria-label","Accessible city map without 3D graphics");
    panel.style.cssText="width:min(100%,760px);margin:0 auto;padding:1rem;box-sizing:border-box;background:#0a2230;color:#f3f8f6;border:2px solid #4cae9a;border-radius:16px";
    canvas.insertAdjacentElement("afterend",panel);
  }
  const city=cityById(game);
  const description=document.createElement("p");
  description.setAttribute("role","status");
  description.textContent="3D graphics are not available on this device. Your original city is playable on this accessible 2D map. Choose a tile, then use the existing Build controls.";
  const grid=document.createElement("div");
  grid.style.cssText="display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:4px;margin-top:12px";
  for(let z=0;z<9;z++)for(let x=0;x<9;x++){
    const building=city.buildings.find(b=>b.x===x&&b.z===z);
    const ground=terrain(x,z,city.seed,city.biome),free=isBuildable(city,x,z);
    const selected=selection.x===x&&selection.z===z;
    const tile=document.createElement("button");tile.type="button";
    const label=building?(BUILDINGS[building.type]?.name||"Existing building"):ground;
    tile.textContent=building?(BUILDINGS[building.type]?.icon||"⌂"):(free?"·":"≈");
    tile.setAttribute("aria-label","Tile "+x+":"+z+", "+label+(free?", buildable":""));
    tile.setAttribute("aria-pressed",String(selected));
    tile.style.cssText="min-width:0;min-height:36px;border:1px solid #679b9c;border-radius:5px;cursor:pointer;font-size:1.1rem;color:#fff;background:"+
      (selected?"#846927":building?"#326754":free?"#244e4d":"#173b53");
    tile.addEventListener("click",()=>{
      selection={x,z};if(tab!=="build")setTab("build");else updatePanel();
      renderFallbackWorld();
    });
    grid.append(tile);
  }
  panel.replaceChildren(description,grid);
}
'''


REPLACEMENTS = (
    (
        '  BUILDINGS, BIOMES, RESOURCES, EXPLORATION_COST, TACTICS, HEROES,',
        '  BUILDINGS, BIOMES, RESOURCES, EXPLORATION_COST, TACTICS, HEROES, terrain,',
    ),
    (
        'let renderer;\ntry{renderer=new WorldRenderer($("#world"));}\n'
        'catch(e){$("#world").style.display="none";$("#panelTitle").textContent="3D unavailable";'
        '$("#panelBody").textContent="This game needs a browser with WebGL 2 enabled. "+e.message;}',
        'let renderer;\ntry{renderer=new WorldRenderer($("#world"));}\n'
        'catch(e){$("#world").style.display="none";}\n' + FALLBACK,
    ),
    (
        'function update(){updateHud();updatePanel();}',
        'function update(){updateHud();updatePanel();renderFallbackWorld();}',
    ),
    (
        'canvas.addEventListener("webglcontextlost",e=>{e.preventDefault();renderer=null;flash("3D graphics were paused. Restoring the scene…");});',
        'canvas.addEventListener("webglcontextlost",e=>{e.preventDefault();renderer=null;renderFallbackWorld();flash("3D graphics were paused. Restoring the scene…");});',
    ),
    (
        '  try{renderer=new WorldRenderer(canvas);flash("3D scene restored.");}\n'
        '  catch(_e){flash("Graphics recovery failed. Reload the page.");}',
        '  try{renderer=new WorldRenderer(canvas);renderFallbackWorld();flash("3D scene restored.");}\n'
        '  catch(_e){renderFallbackWorld();flash("3D graphics remain unavailable; the 2D map still works.");}',
    ),
)


def patch_source(source: str) -> str:
    if 'function renderFallbackWorld()' in source:
        raise ValueError('already_patched')
    updated = source
    for old, new in REPLACEMENTS:
        if updated.count(old) != 1:
            raise ValueError('unexpected_original_source_signature')
        updated = updated.replace(old, new, 1)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', help='Existing app.mjs source; use - for stdin', required=True)
    parser.add_argument('--expected-sha256', help='Exact SHA-256 of the original release asset', required=True)
    args = parser.parse_args()
    if args.source == '-':
        original = sys.stdin.buffer.read()
    else:
        path = Path(args.source)
        if path.is_symlink() or not path.is_file():
            parser.error('source file unavailable or symbolic link')
        original = path.read_bytes()
    if hashlib.sha256(original).hexdigest() != args.expected_sha256.lower():
        parser.error('source hash mismatch; nothing emitted')
    if len(original) > 2_000_000:
        parser.error('unexpected source size; nothing emitted')
    try:
        candidate = patch_source(original.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as error:
        parser.error(f'{error}; nothing emitted')
    sys.stdout.buffer.write(candidate.encode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

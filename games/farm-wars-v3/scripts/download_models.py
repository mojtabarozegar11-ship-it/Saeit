#!/usr/bin/env python3
"""Download pinned CC0 Kenney GLB assets for the self-hosted Farm Dominion renderer.

Source: Hidencod/tge-assets asset mirror, Kenney original creator, CC0-1.0.
The exact revision is pinned; all files must be independent binary glTF/GLB.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, Request
import struct, time, hashlib
ROOT = Path(__file__).resolve().parent.parent
MODEL_MANIFEST = ROOT / "models.txt"
PINNED_REVISION = "2c8950b716e6765930b2b51409c59adf3d66fd5c"
OUT = ROOT / "build" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
entries=[]
for line in MODEL_MANIFEST.read_text("utf-8").splitlines():
    if not line.strip():
        continue
    label, source = line.split("|", 1)
    assert label.replace("-","").isalnum() and ".." not in source and "/" in source
    entries.append((label,source))
assert len(entries)>=24 and len({e[0] for e in entries})==len(entries)
def fetch(entry):
    label, path = entry
    url=f"https://raw.githubusercontent.com/Hidencod/tge-assets/{PINNED_REVISION}/packs/{path}"
    err=None
    for attempt in range(1,4):
        try:
            with urlopen(Request(url,headers={"User-Agent":"ZomorodFarmDominionCC0/3.0"}),timeout=40) as resp:
                binary=resp.read(2_500_000)
            assert len(binary)>1000 and binary[:4]==b"glTF", f"{label}: not a GLB"
            version, declared_size=struct.unpack_from("<II",binary,4)
            assert version==2 and declared_size==len(binary), f"{label}: truncated or corrupt"
            file=OUT/(label+".glb")
            file.write_bytes(binary)
            return label,len(binary),hashlib.sha256(binary).hexdigest()
        except Exception as e:
            err=e
            time.sleep(attempt*1.3)
    raise RuntimeError(f"Could not fetch pinned asset {label}: {err}")
with ThreadPoolExecutor(max_workers=7) as pool:
    pending=[pool.submit(fetch,e) for e in entries]
    for task in as_completed(pending):
        label,size,digest=task.result()
        print("FARM_3D_ASSET=OK",label,size,digest[:14],flush=True)
assert len(list(OUT.glob("*.glb")))==len(entries)
print("FARM_3D_ASSETS_ALL=PASS",len(entries))

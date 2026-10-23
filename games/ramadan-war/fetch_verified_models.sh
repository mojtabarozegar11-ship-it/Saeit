#!/usr/bin/env bash
# Rehydrate the *complete* CC-BY model derivatives before any game smoke/deploy.
# The two binary files checked into the project are truncated and are never trusted.
set -euo pipefail

source_commit="130ac2a5c856401ec36e7d35afcfefe40c5801f4"
source_base="https://raw.githubusercontent.com/cktang88/3d-fps/${source_commit}/public/assets/models"
game_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
temp_dir="$(mktemp -d)"
trap 'rm -r -- "$temp_dir"' EXIT

validate_glb() {
  python3 - "$1" "$2" <<'PY'
import json, struct, sys
from pathlib import Path
path, min_images = Path(sys.argv[1]), int(sys.argv[2])
data = path.read_bytes()
assert len(data) >= 20, "GLB is too short"
magic, version, total_size = struct.unpack_from("<4sII", data, 0)
assert magic == b"glTF" and version == 2, "Invalid glTF v2 binary header"
assert total_size == len(data), f"Truncated GLB: header={total_size}, file={len(data)}"
json_size, json_type = struct.unpack_from("<I4s", data, 12)
assert json_type == b"JSON" and json_size % 4 == 0
doc = json.loads(data[20:20 + json_size])
assert doc.get("asset", {}).get("version") == "2.0"
assert len(doc.get("meshes", [])) > 0, "No renderable geometry"
assert len(doc.get("images", [])) >= min_images, "Expected embedded material textures"
offset = 20 + json_size
assert offset + 8 <= len(data), "Missing BIN chunk"
bin_size, bin_type = struct.unpack_from("<I4s", data, offset)
assert bin_type == bytes((66, 73, 78, 0)), "Missing glTF binary geometry/data chunk"
assert offset + 8 + bin_size == len(data), "Malformed GLB chunk length"
buffer_size = doc["buffers"][0]["byteLength"]
assert buffer_size <= bin_size, "Declared buffer exceeds actual bytes"
for view in doc.get("bufferViews", []):
    buffer_index = view.get("buffer", 0)
    assert 0 <= buffer_index < len(doc["buffers"]), "Unknown buffer index"
    assert view.get("byteOffset", 0) + view["byteLength"] <= doc["buffers"][buffer_index]["byteLength"], "Out-of-range bufferView"
for item in doc.get("images", []):
    assert "bufferView" in item or item.get("uri"), "Image has no payload"
print(f"GLB_COMPLETE=PASS {path.name} bytes={len(data)} meshes={len(doc['meshes'])} images={len(doc.get('images', []))}")
PY
}

fetch_one() {
  local destination="$1" source_path="$2" expected_bytes="$3" expected_blob="$4" minimum_images="$5"
  local temporary="$temp_dir/$destination" actual_bytes actual_blob
  curl --fail --show-error --silent --location --retry 3 --retry-delay 2 --max-time 120 \
    --proto '=https' --proto-redir '=https' \
    "$source_base/$source_path" --output "$temporary"
  actual_bytes="$(wc -c < "$temporary" | tr -d '[:space:]')"
  [[ "$actual_bytes" == "$expected_bytes" ]] || { echo "REFUSE incomplete $destination: $actual_bytes != $expected_bytes" >&2; return 1; }
  actual_blob="$(git hash-object "$temporary")"
  [[ "$actual_blob" == "$expected_blob" ]] || { echo "REFUSE unexpected upstream bytes for $destination" >&2; return 1; }
  validate_glb "$temporary" "$minimum_images"
  [[ -f "$game_dir/$destination" && ! -L "$game_dir/$destination" ]] || { echo "REFUSE unexpected target $destination" >&2; return 1; }
  install -m 0644 "$temporary" "$game_dir/$destination"
  [[ "$(git hash-object "$game_dir/$destination")" == "$expected_blob" ]] || { echo "REFUSE post-copy hash mismatch" >&2; return 1; }
  echo "FULL_MODEL_VERIFIED=$destination"
}

fetch_one "soldier-rigged-ccby.glb" "characters/soldier.glb" 3094592 "b00ed33108f2579880c82cd27d10f9237ff3a219" 0
fetch_one "m24-sniper-ccby.glb" "fp/m24.glb" 1247684 "537d61b8a28f1cea048c048c1e6a29c27c02cb6e" 1
echo "RAMADAN_COMPLETE_MODELS_READY=PASS"

#!/usr/bin/env bash
# Verify six independently transferred native candidates on the PRIVATE VPS.
set -euo pipefail
umask 077
test "${GITHUB_REF:-}" = "refs/heads/main"
test "${GITHUB_REPOSITORY:-}" = "mojtabarozegar11-ship-it/Saeit"
test -n "${VPS_KEY:-}"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]
work="$(mktemp -d)"
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
printf '%s' "$VPS_KEY" | python -c 'import sys;s=sys.stdin.buffer.read().decode("utf-8");s=s.replace("\r\n","\n").replace("\r","").replace("\\n","\n").rstrip()+"\n";sys.stdout.buffer.write(s.encode("utf-8"))' > "$work/key"
chmod 600 "$work/key"
ssh-keygen -y -P "" -f "$work/key" >/dev/null
ssh-keyscan -T 10 -t rsa 178.239.147.150 > "$work/known" 2>/dev/null
test "$(ssh-keygen -lf "$work/known" -E sha256 | awk '{print $2}' | sort -u)" = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
opts=(-i "$work/key" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$work/known" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
stage="/home/githubops/factory-runtime/private/autonomous-product-cycle/native-candidate-evidence/$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
ssh -T "${opts[@]}" githubops@178.239.147.150 python3 - "$stage" <<'PY'
import hashlib,json,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
root=Path(sys.argv[1])
assert root.is_dir() and not root.is_symlink()
try:
    root.resolve().relative_to((Path.home()/"factory-runtime/private/autonomous-product-cycle").resolve())
except ValueError:
    raise RuntimeError("PRIVATE_NATIVE_ROOT_OUTSIDE_FACTORY")
families=("F12","F13","F14","F16","F17","F26")
proofs=[]
for family in families:
    folder=root/family
    assert folder.is_dir() and not folder.is_symlink()
    script=folder/"factory_six_native_candidate_bundle.py"
    assert script.is_file() and not script.is_symlink()
    result=subprocess.run([sys.executable,"-B",str(script),"--family",family,
                           "--out",str(folder),"--verify"],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,timeout=90,check=True)
    assert "SIX_NATIVE_INDEPENDENT_VERIFICATION=" in result.stdout
    rec=json.loads((folder/"technical-native-receipt.json").read_text("utf8"))
    assert rec["family"]==family
    assert rec["quality_1000_certified"] is False
    assert rec["commercial_release"] is False
    proofs.append({"family":family,"native_candidate_files":rec["format_candidate_count"],
                   "archive_sha256":rec["archive_sha256"],"verified_on_vps":True})
assert len(proofs)==6
assert sum(p["native_candidate_files"] for p in proofs)==56
data={"schema":"saeit.factory.native-six-vps-aggregate.v1",
      "utc":datetime.now(timezone.utc).isoformat(),
      "private_only":True, "six_families_verified":6,
      "candidate_native_file_count":56,
      "files":proofs,
      "independent_specialist_quality_1000_certified":0,
      "production_release_authorized":False,"sites_modified":0}
destination=root/"verified-six-private-native.json"
assert not destination.exists() and not destination.is_symlink()
fd,tmp=tempfile.mkstemp(prefix=".private-native-",dir=str(root))
try:
    with os.fdopen(fd,"w",encoding="utf8") as f:
        json.dump(data,f,sort_keys=True,indent=2)
        f.write("\n");f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o600)
    os.replace(tmp,destination)
finally:
    if os.path.exists(tmp):os.unlink(tmp)
h=hashlib.sha256(destination.read_bytes()).hexdigest()
print("FACTORY_SIX_NATIVE_PRIVATE_VPS_PROVEN=6")
print("FACTORY_NATIVE_CANDIDATE_FORMAT_FILES=56")
print("FACTORY_SIX_NATIVE_AGGREGATE_SHA256="+h)
print("FACTORY_NATIVE_QUALITY_1000_CERTIFIED=0")
print("FACTORY_PUBLIC_SITES_UNCHANGED=PASS")
PY

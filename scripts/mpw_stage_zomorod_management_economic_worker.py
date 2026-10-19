"""Install only a SHA-verified reporting/economic policy script into private MPW."""
import hashlib,os,re,sys
from pathlib import Path
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_intelligence_20261018")
TARGET=ROOT/"worker.py"
def main():
    if len(sys.argv)!=2 or not re.fullmatch("[0-9a-f]{64}",sys.argv[1]):raise SystemExit("HASH_REQUIRED")
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.stat().st_mode&0o077:raise SystemExit("PRIVATE_SOURCE_INVALID")
    if TARGET.exists() or TARGET.is_symlink():raise SystemExit("NO_OVERWRITE")
    data=sys.stdin.buffer.read(60001)
    if not data or len(data)>60000 or hashlib.sha256(data).hexdigest()!=sys.argv[1]:
        raise SystemExit("HASH_MISMATCH")
    fd=os.open(str(TARGET),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if hashlib.sha256(TARGET.read_bytes()).hexdigest()!=sys.argv[1]:
        TARGET.unlink();raise SystemExit("COPY_VERIFICATION_FAILED")
    print("MPW_ZOMOROD_MANAGEMENT_ECONOMIC_WORKER_STAGED=1")
if __name__=="__main__":main()

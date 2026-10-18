"""Write only verified source reviewer into a fresh private MPW quality-agent directory."""
import hashlib,os,re,sys,shutil
from pathlib import Path
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST=ROOT/"quality_review_agent_20261018"
PROGRAM=DEST/"review_private_drafts.py"
def main():
    assert len(sys.argv)==2 and re.fullmatch(r"[a-f0-9]{64}",sys.argv[1])
    assert ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode&0o077==0
    assert not DEST.exists() and not DEST.is_symlink()
    buf=sys.stdin.buffer.read(55000)
    assert buf and len(buf)<55000 and hashlib.sha256(buf).hexdigest()==sys.argv[1]
    DEST.mkdir(mode=0o700)
    try:
        fd=os.open(str(PROGRAM),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:f.write(buf);f.flush();os.fsync(f.fileno())
        assert hashlib.sha256(PROGRAM.read_bytes()).hexdigest()==sys.argv[1]
        print("MPW_QUALITY_REVIEWER_SHA256_STAGED_PRIVATE=1")
    except BaseException:
        shutil.rmtree(DEST,ignore_errors=True)
        raise
if __name__=="__main__":main()

"""Private SQLite storage for no-account MojPlayWin guest orders."""
import os,sqlite3
from pathlib import Path
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
FILE=ROOT/"mpw_guest_trx_v1.sqlite3"
CREATE="""CREATE TABLE IF NOT EXISTS guest_orders(
id INTEGER PRIMARY KEY AUTOINCREMENT,
claim_sha TEXT UNIQUE NOT NULL,
product_id INTEGER NOT NULL,
usd TEXT NOT NULL,
rate TEXT NOT NULL,
amount_sun INTEGER NOT NULL UNIQUE,
sender TEXT NOT NULL,
receiver TEXT NOT NULL,
issued_ms INTEGER NOT NULL,
expires_ms INTEGER NOT NULL,
txid TEXT UNIQUE,
status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid'))
)"""
def connect():
 if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.stat().st_mode & 0o077:
  raise RuntimeError("Guest private storage unavailable")
 if FILE.is_symlink():
  raise RuntimeError("Guest storage path invalid")
 fd=os.open(str(FILE),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 os.close(fd)
 conn=sqlite3.connect(str(FILE),timeout=5)
 conn.row_factory=sqlite3.Row
 conn.execute(CREATE)
 return conn

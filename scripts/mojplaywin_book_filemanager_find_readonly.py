#!/usr/bin/env python3
"""Read-only bounded lookup of two owner-mentioned book files in cPanel File Manager.

Does not open file contents, access databases/secrets, follow symlinks, or
modify anything. Only candidate filenames and file sizes are reported.
"""
import json
import os
import time
from pathlib import Path

HOME = Path("/home/zomorod2")
EXCLUDES = {".ssh", ".git", ".cache", ".npm", "node_modules", "__pycache__", "venv", ".venv", "site-packages", "vendor", "logs", "log", ".cpanel", "mail", "etc", "ssl", ".trash", "tmp", ".local", ".config", ".mozilla", ".rustup", ".cargo", ".snapshots", "backup", "backups"}
TOKENS = {
    "chess": ("chess", "shatranj", "shatrang", "شطرنج", "chess_improvement", "grandmaster"),
    "taniya": ("taniya", "tanya", "tania", "bakery", "worms", "worm", "little_baker", "تانیا", "قصه", "داستان"),
}
ALLOWED_EXT = {".pdf", ".epub", ".mobi", ".zip", ".rar", ".docx", ".doc", ".webp", ".jpeg", ".jpg", ".png", ".avif", ".cbz"}
MAX_FILES=80000
MAX_SECONDS=38
START=time.monotonic()
matches=[]
scanned=0
blocked=0
errors=0

def accept_dir(dirname):
    x=dirname.lower()
    return x not in EXCLUDES and not x.startswith(".") and x not in ("wheels", "dist-packages", "build", "staticfiles")

try:
    for base, dirs, files in os.walk(HOME, topdown=True, followlinks=False):
        if time.monotonic()-START>MAX_SECONDS or scanned>MAX_FILES: break
        dirs[:] = [d for d in dirs if accept_dir(d) and not os.path.islink(os.path.join(base,d))]
        for fn in files:
            scanned+=1
            if scanned>MAX_FILES or time.monotonic()-START>MAX_SECONDS:break
            path=Path(base)/fn
            ext=path.suffix.lower()
            name=fn.casefold()
            kind=next((key for key,words in TOKENS.items() if ext in ALLOWED_EXT and any(term in name for term in words)), None)
            if not kind:continue
            try:
                if path.is_symlink() or not path.is_file():continue
                stat=path.stat()
                if stat.st_size>1_500_000_000:continue
                matches.append({"book":kind,"relative_path":str(path.relative_to(HOME)), "extension":ext,"bytes":stat.st_size})
            except OSError:errors+=1
            if len(matches)>=35:break
        if len(matches)>=35:break
except OSError:
    errors+=1

print(json.dumps({"classification":"BOOK_FILE_MANAGER_FILENAME_INVENTORY_READONLY","candidates":matches,"scanned_file_names":scanned,"truncated":scanned>=MAX_FILES or time.monotonic()-START>MAX_SECONDS or len(matches)>=35,"elapsed_seconds":round(time.monotonic()-START,2),"file_data_read":False,"site_changed":False,"errors":errors},ensure_ascii=False))

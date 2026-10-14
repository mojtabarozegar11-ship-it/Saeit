#!/usr/bin/env python3
"""Prepare the fixed MojPlayWin chess ebook assets. Never publishes a product or starts payments.

Usage:
  python3 scripts/mojplaywin_chess_assets.py --verify
  python3 scripts/mojplaywin_chess_assets.py --install

Run only after the owner uploads the approved ZIP to the private cPanel directory.
All files are checksum-verified and remain outside website document roots.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

HOME = Path("/home/zomorod2")
INCOMING = HOME / "MojPlayWin_Private_Uploads" / "MojPlayWin_Chess_Product_Assets_2026-10-14.zip"
TARGET_PARENT = HOME / "MojPlayWin_Private_Assets"
TARGET = TARGET_PARENT / "chess-improvement-2026"
PRODUCT_ID = "mojplaywin-chess-improvement-2026"
FILES = {
    "MojPlayWin_Science_and_Practice_of_Chess_Improvement.pdf": (
        432386, "d284d559bfac931cffe11e97561ac442d63dae5d8eda4bc04e84dd2c26022a1b"
    ),
    "MojPlayWin_Chess_Improvement_Poster_English_50_Off.png": (
        1594834, "c78cce353fb309da7d5a996344c52f8ccb4a7142f2972f4181eb3841a5a8160d"
    ),
    "MojPlayWin_Chess_Improvement_English_Sales_Copy.md": (
        1151, "e925b0393d6e73ac172bae3a1621c0330eab43e061221c1aa058be4ebaeb5f5e"
    ),
    "MojPlayWin_Chess_Improvement_Asset_Manifest.json": (
        715, "161f086f02095739725ac81e8282cc9407a548ab6d85f99126d0b7f609329ca5"
    ),
}
MAX_ZIP_BYTES = 4_000_000

def inspect_zip(path=INCOMING):
    if not path.is_file() or path.is_symlink():
        raise ValueError("ZIP missing or is a symlink")
    if path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP exceeds approved size limit")
    output = {}
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        names = [x.filename for x in members]
        if len(names) != len(FILES) or set(names) != set(FILES):
            raise ValueError("ZIP members differ from approved asset list")
        if any(x.is_dir() or "/" in x.filename or "\\" in x.filename for x in members):
            raise ValueError("Unexpected directory or traversal in ZIP")
        for info in members:
            size, digest = FILES[info.filename]
            if info.file_size != size:
                raise ValueError("Size mismatch for " + info.filename)
            if ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                raise ValueError("Symlinks are forbidden")
            with z.open(info) as stream:
                data = stream.read(size + 1)
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("SHA-256 mismatch for " + info.filename)
            if info.filename.endswith(".pdf") and not data.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF file signature")
            if info.filename.endswith(".png") and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Invalid PNG file signature")
            output[info.filename] = data
    manifest = json.loads(output["MojPlayWin_Chess_Improvement_Asset_Manifest.json"].decode("utf-8"))
    if manifest.get("id") != PRODUCT_ID or manifest.get("product_id_in_live_database") != 72:
        raise ValueError("Product reference mismatch")
    return output

def verify_installed(target=TARGET):
    if not target.is_dir() or target.is_symlink():
        return False
    for name, (size, digest) in FILES.items():
        path = target / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size != size:
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True

def install_assets(path=INCOMING, target=TARGET):
    assets = inspect_zip(path)
    parent = target.parent
    if not str(target).startswith(str(HOME / "MojPlayWin_Private_Assets") + os.sep):
        raise ValueError("Target must remain in the approved private storage root")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent.chmod(0o700)
    if target.exists() or target.is_symlink():
        if verify_installed(target):
            print("ALREADY_INSTALLED_AND_VERIFIED")
            return
        raise ValueError("Target exists but is not identical; refusing to overwrite")
    tmp = Path(tempfile.mkdtemp(prefix=".pending-chess-", dir=str(parent)))
    try:
        tmp.chmod(0o700)
        for name, data in assets.items():
            f = tmp / name
            with f.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            f.chmod(0o600)
        if not verify_installed(tmp):
            raise ValueError("Staged files failed second checksum verification")
        tmp.rename(target)
        print("PRIVATE_ASSETS_INSTALLED_AND_VERIFIED")
        print("PRIVATE_PDF_READY (not publicly downloadable)")
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)

def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", action="store_true")
    action.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.verify:
        assets = inspect_zip()
        print("APPROVED_ZIP_VERIFIED", len(assets), "files")
    else:
        install_assets()

if __name__ == "__main__":
    main()

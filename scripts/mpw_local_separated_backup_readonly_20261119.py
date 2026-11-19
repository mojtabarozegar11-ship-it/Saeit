"""Verify only the two owner-local archive files, without extracting or exporting."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile

ROOT = Path("/home/zomorod2/separated-backups/20261119")
FILES = {
    "store_code": "mojplaywin-store-code-20261119.tar.gz",
    "email": "mojplaywin-email-mailboxes-20261119.tar.gz",
}


def inspect():
    report = {"read_only": True, "database_backup_verified": False,
              "restore_verified": False, "external_transfer": False, "archives": {}}
    for role, name in FILES.items():
        result = {"present": False, "private": False, "bytes": 0,
                  "sha256_matches": False, "tar_readable": False}
        report["archives"][role] = result
        path = ROOT / name
        try:
            if any(p.is_symlink() for p in (ROOT, ROOT.parent, path)):
                continue
            st = path.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
                continue
            result["present"] = True
            result["bytes"] = st.st_size
            result["private"] = not bool(st.st_mode & 0o077)
            if not result["private"] or not 0 < st.st_size <= 2_000_000_000:
                continue
            manifest = ROOT / "SHA256SUMS.txt"
            ms = manifest.lstat()
            if not stat.S_ISREG(ms.st_mode) or ms.st_uid != os.getuid() or ms.st_size > 8192 or ms.st_mode & 0o077:
                continue
            with manifest.open("r", encoding="ascii") as source:
                entries = [line.split(maxsplit=1) for line in source]
            expected = [parts[0] for parts in entries if len(parts) == 2 and parts[1].strip() == str(path)]
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            result["sha256_matches"] = len(expected) == 1 and digest.hexdigest() == expected[0]
            if not result["sha256_matches"]:
                continue
            with tarfile.open(path, "r:gz") as archive:
                count = 0
                for member in archive:
                    count += 1
                    if count > 500000:
                        raise ValueError("archive member limit")
                result["tar_readable"] = count > 0
            final = path.stat()
            if (st.st_ino, st.st_size, st.st_mtime_ns) != (final.st_ino, final.st_size, final.st_mtime_ns):
                result["sha256_matches"] = result["tar_readable"] = False
        except (OSError, ValueError, tarfile.TarError):
            continue
    return report


if __name__ == "__main__":
    print("MPW_LOCAL_BACKUP_READONLY=" + json.dumps(inspect(), sort_keys=True))

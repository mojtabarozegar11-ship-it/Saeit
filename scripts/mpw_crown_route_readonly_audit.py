#!/usr/bin/env python3
"""Read-only route audit for MojPlayWin Crown Defender alias.

Never emits credentials, environment values, or unfiltered .htaccess content.
"""
from pathlib import Path
import hashlib

root = Path("/home/zomorod2/mojplaywin.com")
print("CROWN_ROUTE_ROOT_EXISTS", root.is_dir(), "SYMLINK", root.is_symlink())
for rel in (
    ".htaccess", "games", "games/.htaccess", "games/crown-defender",
    "games/corwn-defender", "design-preview-20261017",
    "design-preview-20261017/mpw-crown-defender-20261019",
    "design-preview-20261017/.htaccess",
):
    path = root / rel
    print("CROWN_ROUTE_PATH", rel, "DIR", path.is_dir(), "FILE", path.is_file(), "LINK", path.is_symlink())
    if path.is_file() and not path.is_symlink() and path.name == ".htaccess":
        data = path.read_bytes()
        print("CROWN_HTACCESS_SHA256", rel, hashlib.sha256(data).hexdigest(), "BYTES", len(data))
        count = 0
        for line_no, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            line = line.strip()
            lower = line.lower()
            if not line or line.startswith("#"):
                continue
            if any(secret in lower for secret in ("pass", "secret", "token", "authorization", "cookie", "key=")):
                continue
            if (line.startswith(("RewriteRule", "RewriteCond", "Redirect", "Alias", "DirectoryIndex"))
                    or "crown" in lower or "/games" in lower):
                print("CROWN_ROUTE_RULE", rel, line_no, line[:220])
                count += 1
                if count >= 75:
                    print("CROWN_ROUTE_RULE_LIMIT_REACHED")
                    break
print("CROWN_ROUTE_AUDIT_COMPLETE")

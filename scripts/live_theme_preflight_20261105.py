#!/usr/bin/env python3
"""Read-only, redacted live-template inventory on the verified cPanel host.

This script never writes, submits a form, or prints file contents. It reports
only the existence, digest and public-template UI markers of candidate files.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
from pathlib import Path


ROOT = Path("/home/zomorod2")
CANDIDATES = {
    "mpw_store_django": ROOT / "Saeit-staging/core/templates/mojplaywin/store.html",
    "mpw_site_base": ROOT / "Saeit-staging/core/templates/mojplaywin/site_base.html",
    "zm_store_public_html": ROOT / "public_html/store/index.php",
    "zm_store_domain_root": ROOT / "zomorodmelal.ir/store/index.php",
    "zm_store_repo_copy": ROOT / "Saeit-staging/content/zomorod-v11/store_index.php",
    "zm_management_public_html": ROOT / "public_html/business/app.php",
    "zm_management_domain_root": ROOT / "zomorodmelal.ir/business/app.php",
    "zm_management_repo_copy": ROOT / "Saeit-staging/content/zomorod-business/app.php",
}


def inventory(label: str, path: Path) -> dict[str, object]:
    row: dict[str, object] = {"label": label, "path": str(path)}
    if path.is_symlink():
        row["status"] = "SYMLINK_NOT_READ"
        return row
    if not path.is_file():
        row["status"] = "NOT_PRESENT"
        return row
    if path.stat().st_size > 2_500_000:
        row["status"] = "TOO_LARGE_NOT_READ"
        return row

    data = path.read_bytes()
    text = data.decode("utf-8", "replace").lower()
    row.update(
        status="PRESENT",
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        selectors={
            "navigation": "<nav" in text,
            "canonical": 'rel="canonical"' in text or "rel='canonical'" in text,
            "viewport": 'name="viewport"' in text or "name='viewport'" in text,
            "guest_checkout_72": "/commerce/book/72/" in text,
            "old_login_checkout_72": "/store/product/72/checkout/" in text,
            "bank_payment_disabled": "پرداخت آنلاین تا اتصال درگاه غیرفعال است" in text,
            "management_label_for": 'for="business-login-password"' in text,
        },
    )
    return row


def main() -> None:
    # This diagnostic is tied to the previously verified cPanel account.
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise SystemExit("UNEXPECTED_CPANEL_USER")
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise SystemExit("CPANEL_HOME_UNAVAILABLE")

    report = [inventory(label, path) for label, path in CANDIDATES.items()]
    print("LIVE_THEME_READ_ONLY_INVENTORY=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

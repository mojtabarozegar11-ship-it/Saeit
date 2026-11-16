"""Owner-only read-only parity between public GET and actual cPanel static HTML.

Never prints HTML, noncanonical option values, customer info, paths, or secrets.
A true can_surgically_repair is only a diagnostic, NOT permission to write.
"""
from __future__ import annotations
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

ACCOUNT = "zomorod2"
FILE = Path("/home/zomorod2/mojplaywin.com/moj-prop/index.html")
MAX_BYTES = 512_000
EXPECTED = ("urgent", "week", "month", "review")
LABELS = ("Today / urgent", "This week", "This month", "Initial review only")


class Horizon(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_select = False
        self.option = False
        self.values = []
        self.labels = []
        self.parts = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "select" and (attrs.get("id") == "horizon"
                                 or attrs.get("name") == "horizon"):
            if self.in_select:
                raise ValueError("nested select")
            self.in_select = True
        elif tag == "option" and self.in_select:
            self.option = True
            self.values.append(attrs.get("value"))
            self.parts = []

    def handle_data(self, text):
        if self.in_select and self.option:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == "option" and self.option:
            self.labels.append(" ".join("".join(self.parts).split()))
            self.option = False
            self.parts = []
        elif tag == "select" and self.in_select:
            self.in_select = False


def classify(data: bytes, http_digest: str) -> dict:
    result = {
        "schema": "mojprop.cpanel.horizon_parity.readonly.c125.v1",
        "read_only": True,
        "owner_account_verified": False,
        "safe_file_identity_verified": False,
        "disk_file_present": False,
        "public_http_matches_disk": False,
        "four_options_found": False,
        "option_labels_exact_reviewed": False,
        "horizon_values_canonical": False,
        "surgical_value_only_candidate": False,
        "writes_or_customer_records_accessed": False,
        "independent_backup_verified": False,
        "production_change_authorized": False,
    }
    if (type(data) is not bytes or not 0 < len(data) <= MAX_BYTES
            or type(http_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", http_digest) is None):
        return result
    result["disk_file_present"] = True
    result["public_http_matches_disk"] = (
        hashlib.sha256(data).hexdigest() == http_digest
    )
    try:
        p = Horizon()
        p.feed(data.decode("utf-8", "strict"))
        p.close()
    except (UnicodeDecodeError, ValueError):
        return result
    result["four_options_found"] = len(p.values) == 4 and len(p.labels) == 4
    result["option_labels_exact_reviewed"] = tuple(p.labels) == LABELS
    result["horizon_values_canonical"] = tuple(p.values) == EXPECTED
    values_bounded = all(
        type(x) is str and re.fullmatch(r"[a-z][a-z_]{0,30}", x) is not None
        for x in p.values
    ) and len(set(p.values)) == 4
    result["surgical_value_only_candidate"] = (
        result["public_http_matches_disk"] and result["four_options_found"]
        and result["option_labels_exact_reviewed"] and values_bounded
        and not result["horizon_values_canonical"]
    )
    return result


def main(argv):
    report = classify(b"", "")
    try:
        if (len(argv) != 2 or pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT
                or os.geteuid() == 0):
            raise ValueError("wrong account or invocation")
        report["owner_account_verified"] = True
        route = FILE.parent
        root = route.parent
        if any(p.is_symlink() for p in (root, route, FILE)):
            raise ValueError("symlink blocked")
        if not root.is_dir() or not route.is_dir():
            raise ValueError("wrong docroot")
        st = FILE.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_size > MAX_BYTES or st.st_mode & 0o002):
            raise ValueError("unsafe file")
        report["safe_file_identity_verified"] = True
        with FILE.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        observed = classify(data, argv[1])
        observed["owner_account_verified"] = True
        observed["safe_file_identity_verified"] = True
        report = observed
    except (OSError, ValueError, KeyError):
        pass
    print("MOJPROP_CPANEL_HORIZON_C125=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv)

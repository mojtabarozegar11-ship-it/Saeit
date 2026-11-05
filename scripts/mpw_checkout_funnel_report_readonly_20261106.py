#!/usr/bin/env python3
"""Read only on-site anonymous checkout event totals. No customer access."""
import json
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("no arguments expected")
    sys.path.insert(0, str(APP))
    from services.mpw_checkout_funnel import report
    print(json.dumps(report(7), sort_keys=True))

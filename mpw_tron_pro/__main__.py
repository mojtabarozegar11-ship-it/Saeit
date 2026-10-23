"""Run development preview only: python -m mpw_tron_pro --preview [port]."""
import sys
from .webapp import run_preview
if __name__ == '__main__':
    if len(sys.argv) not in (2, 3) or sys.argv[1] != '--preview':
        raise SystemExit('Run: python -m mpw_tron_pro --preview [local_port] (NO real payments)')
    run_preview(int(sys.argv[2]) if len(sys.argv) == 3 else 8765)
"""Construct a disabled, offline-only browser review file. No money allowed."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mpw_tron_pro.webapp import render_checkout, ASSETS
root=Path(__file__).resolve().parents[1]
page=render_checkout(None,preview=True).decode()
page=page.replace('<link rel="stylesheet" href="/assets/checkout.css">',
                  '<style>'+ (ASSETS/'checkout.css').read_text()+'</style>')
page=page.replace('<script src="/assets/checkout.js" defer></script>',
                  '<script>'+ (ASSETS/'checkout.js').read_text()+'</script>')
out=root/'preview-offline-v03.html'
out.write_text(page)
assert 'NO REAL FUNDS' in page and 'aria-disabled="true"' in page
assert 'https://link.trustwallet.com/send?' not in page
print(out)
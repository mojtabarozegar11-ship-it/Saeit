"""Runtime MOJ PROP package with compatibility lookup for source-only tests.

The legacy source-sync tree remains non-runtime. Extending the package search
path lets historical pure-Python tests import their read-only helpers without
replacing the runtime models or enabling commerce.
"""
from pathlib import Path

_LEGACY_PROP_FIRM = (
    Path(__file__).resolve().parents[1]
    / "source-sync"
    / "20261120"
    / "prop_firm"
)
if _LEGACY_PROP_FIRM.is_dir():
    __path__.append(str(_LEGACY_PROP_FIRM))

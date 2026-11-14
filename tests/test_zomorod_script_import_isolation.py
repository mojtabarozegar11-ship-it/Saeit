"""Keep the existing site release regressions import-safe under pytest.

Guard scripts must only load deployment adapters when explicitly executed as
CLI commands with staged inputs. Collection never accesses cPanel, VPS or
changes the website; this test itself is wholly local and read-only.
"""
import importlib.util
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("name", [
    "test_zomorod_onepass_20261113.py",
    "test_zomorod_vision_ux_20261113.py",
])
def test_site_rollback_scripts_are_import_safe_and_cli_only(name):
    script = Path(__file__).resolve().parents[1] / "scripts" / name
    assert script.is_file()
    # No stage directory exists: importing the script should neither probe
    # a staging path nor eagerly import a deployment adapter.
    with patch.object(
        importlib.util, "spec_from_file_location",
        wraps=importlib.util.spec_from_file_location,
    ) as dynamic_loader, patch.object(
        tempfile, "TemporaryDirectory",
        wraps=tempfile.TemporaryDirectory,
    ) as tmp, patch.object(
        Path, "write_bytes",
        side_effect=AssertionError("collection must not write site fixtures"),
    ):
        namespace = runpy.run_path(str(script), run_name="_pytest_import_only_")
    dynamic_loader.assert_not_called()
    tmp.assert_not_called()
    assert callable(namespace["main"])

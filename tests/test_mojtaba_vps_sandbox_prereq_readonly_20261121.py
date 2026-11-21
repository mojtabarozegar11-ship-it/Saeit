"""Proof that the owner VPS prerequisite census is noninvasive and fail-closed."""
from pathlib import Path
import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "deploy/mojtaba_vps_sandbox_prereq_readonly_20261121.py"
SPEC = importlib.util.spec_from_file_location("mojtaba_vps_sandbox_prereq_readonly", TARGET)
census = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(census)


@pytest.mark.parametrize("candidate,expected", [
    ("0\n", "0"),
    ("10000\n", "10000"),
    ("max\n", "max"),
    ("max 100000\n", "max 100000"),
    ("50000 100000\n", "50000 100000"),
    ("\n", None),
    ("no-value", None),
    ("1000;touch /tmp/bad", None),
    ("0\nSECRET=secret", None),
    ("x" * 100, None),
])
def test_only_safe_numeric_limits_are_accepted(candidate, expected):
    assert census.normalized_scalar(candidate) == expected


def test_symlinked_scalar_is_unknown_not_followed(tmp_path):
    safe = tmp_path / "number"
    safe.write_text("25\n")
    link = tmp_path / "alias"
    link.symlink_to(safe)
    assert census.read_scalar(safe) == "25"
    assert census.read_scalar(link) is None



def test_versioned_python_executable_symlink_is_counted_without_escaping(tmp_path):
    bin_dir = tmp_path / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    versioned = bin_dir / "python3.11"
    versioned.write_bytes(b"readonly dummy executable")
    versioned.chmod(0o755)
    link = bin_dir / "python3"
    link.symlink_to("python3.11")
    with patch.object(census, "BINS", {"python3": link}):
        assert census.trusted_system_binary_present("python3", link) is True
        # Read-only census must not follow caller-chosen paths or chains.
        link.unlink()
        link.symlink_to("../private/python3.11")
        assert census.trusted_system_binary_present("python3", link) is False
        link.unlink()
        link.symlink_to("python3.11")
        versioned.unlink()
        versioned.symlink_to(tmp_path / "outside")
        assert census.trusted_system_binary_present("python3", link) is False


def test_nonpython_executable_symlink_is_not_treated_as_trusted(tmp_path):
    exe = tmp_path / "bwrap.real"
    exe.write_bytes(b"demo")
    exe.chmod(0o755)
    symlink = tmp_path / "bwrap"
    symlink.symlink_to(exe.name)
    assert census.trusted_system_binary_present("bwrap", symlink) is False


def test_missing_scalar_returns_unknown(tmp_path):
    assert census.read_scalar(tmp_path / "absent") is None


def test_process_owner_must_be_exact_existing_service_account():
    with patch.object(census.os, "geteuid", return_value=99), patch.object(
        census.pwd, "getpwuid", return_value=SimpleNamespace(pw_name="other")
    ):
        with pytest.raises(PermissionError, match="EXISTING_GITHUBOPS"):
            census.snapshot()


def test_snapshot_is_aggregate_only_no_secret_network_or_worker_action():
    with patch.object(census.os, "geteuid", return_value=123), patch.object(
        census.pwd, "getpwuid", return_value=SimpleNamespace(pw_name="githubops")
    ), patch.object(census, "read_scalar", return_value=None), patch.object(
        census, "regular_file_present", return_value=False
    ), patch.object(census, "directory_present", return_value=False), patch.object(
        census, "safe_disk_gib", return_value=None
    ), patch.object(census.os, "access", return_value=False):
        row = census.snapshot()
    assert row["schema"] == census.SCHEMA
    assert row["read_only"] is True
    assert row["host_role"] == "vps"
    assert row["security_prerequisites"]["rootless_networkless_sandbox_attested"] is False
    assert row["unknowns"]["canonical_active_worker_verified"] is True
    assert all(value is False for value in row["attestation"].values())
    text = json.dumps(row)
    for forbidden in ("ssh_private_key", "API_KEY=", "password", "process_args", "wallet_seed"):
        assert forbidden not in text


def test_static_contract_never_executes_or_mutates_the_host():
    text = TARGET.read_text()
    assert "os.statvfs(" in text
    assert "pwd.getpwuid(os.geteuid())" in text
    assert "subprocess." not in text
    assert "os.system(" not in text
    assert "os.exec" not in text
    assert "os.environ[" not in text
    assert ".write_text(" not in text
    assert "sysctl -w" not in text
    assert "rootless_networkless_sandbox_attested" in text

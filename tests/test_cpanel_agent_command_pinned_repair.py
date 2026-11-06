"""No-SSH regression checks for the pinned, rollback-safe cPanel command repair."""

import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "deploy/cpanel_site_agent_command_install.py"
SPEC = importlib.util.spec_from_file_location("saeit_command_installer", SOURCE)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def _fixture(tmp_path):
    app = tmp_path / "app"
    stage = tmp_path / "stage"
    installed = app / "core/management/commands"
    staged = stage / "core/management/commands"
    installed.mkdir(parents=True)
    staged.mkdir(parents=True)
    old = b"pinned legacy content\n"
    new = b"corrected knowledge status\n"
    for name in installer.COMMANDS:
        data = old if name == "knowledge_agent_cycle" else b"unchanged command\n"
        (installed / (name + ".py")).write_bytes(data)
        (staged / (name + ".py")).write_bytes(
            new if name == "knowledge_agent_cycle" else data
        )
    return app, stage, installed, old, new


def _fake_run(args, **kwargs):
    return subprocess.CompletedProcess(
        args, 0, stdout="company_activity_agent_cycle\nknowledge_agent_cycle\n"
    )


def test_pinned_status_only_replacement(tmp_path):
    app, stage, installed, old, new = _fixture(tmp_path)
    with (
        patch.object(installer, "verify_runtime"),
        patch.object(installer, "verify_staged_commands"),
        patch.object(installer, "LEGACY_KNOWLEDGE_STATUS_SHA256", hashlib.sha256(old).hexdigest()),
        patch.object(installer.subprocess, "run", side_effect=_fake_run),
    ):
        installer.install(app, stage, Path("/fake/python"), "123")
    assert (installed / "knowledge_agent_cycle.py").read_bytes() == new
    assert not list(installed.glob("*.rollback"))
    assert not list(installed.glob(".*.rollback"))


def test_unrecognized_status_revision_is_never_overwritten(tmp_path):
    app, stage, installed, old, _ = _fixture(tmp_path)
    with (
        patch.object(installer, "verify_runtime"),
        patch.object(installer, "verify_staged_commands"),
    ):
        try:
            installer.install(app, stage, Path("/fake/python"), "123")
        except RuntimeError as exc:
            assert "EXISTING_DIFFERENT" in str(exc)
        else:
            raise AssertionError("Divergent installed command must never be replaced")
    assert (installed / "knowledge_agent_cycle.py").read_bytes() == old


def test_failed_post_install_check_restores_original_inode(tmp_path):
    app, stage, installed, old, _ = _fixture(tmp_path)
    old_path = installed / "knowledge_agent_cycle.py"
    old_inode = old_path.stat().st_ino
    calls = []

    def failing_check(args, **kwargs):
        calls.append(args)
        if args[-1] == "check":
            raise subprocess.CalledProcessError(1, args)
        return _fake_run(args, **kwargs)

    with (
        patch.object(installer, "verify_runtime"),
        patch.object(installer, "verify_staged_commands"),
        patch.object(installer, "LEGACY_KNOWLEDGE_STATUS_SHA256", hashlib.sha256(old).hexdigest()),
        patch.object(installer.subprocess, "run", side_effect=failing_check),
    ):
        try:
            installer.install(app, stage, Path("/fake/python"), "123")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("Expected simulated post-install failure")
    assert old_path.read_bytes() == old
    assert old_path.stat().st_ino == old_inode
    assert len(calls) == 2

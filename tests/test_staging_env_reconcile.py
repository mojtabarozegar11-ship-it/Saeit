"""Regression tests for the redacted, read-only staging env reconciliation gate."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "staging_env_reconcile.py"
spec = importlib.util.spec_from_file_location("staging_env_reconcile", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def sample(**updates):
    values = {
        "SAEIT_ENV": "staging",
        "DEBUG": "False",
        "DATABASE_URL": "postgresql://stage:encoded%40password@127.0.0.1:5432/staging_db",
        "STAGING_DB_IDENTITY": "staging_db",
        "PRODUCTION_DB_IDENTITY": "production_db",
    }
    values.update(updates)
    return values


def test_safe_local_staging_candidate():
    report = gate.inspect(sample())
    assert all(report[key] for key in (
        "postgres", "authority_encoded", "local", "db_matches_stage",
        "db_differs_prod", "staging", "debug_off",
    ))


def test_literal_at_sign_is_rejected():
    assert not gate.inspect(sample(DATABASE_URL="postgresql://stage:bad@secret@127.0.0.1/staging_db"))["authority_encoded"]


def test_wrong_database_identity_is_rejected():
    assert not gate.inspect(sample(STAGING_DB_IDENTITY="another_staging"))["db_matches_stage"]


def test_production_identity_collision_is_rejected():
    assert not gate.inspect(sample(PRODUCTION_DB_IDENTITY="staging_db"))["db_differs_prod"]


def test_sqlite_and_debug_are_rejected():
    result = gate.inspect(sample(DATABASE_URL="sqlite:///db.sqlite3", DEBUG="True"))
    assert not result["postgres"]
    assert not result["debug_off"]


def test_reports_redacted_and_never_approves_automatic_restore(tmp_path, capsys):
    current = tmp_path / "current.env"
    backup = tmp_path / "backup.env"
    current.write_text("\n".join(f"{k}={v}" for k, v in sample(
        DATABASE_URL="sqlite:///db.sqlite3", STAGING_DB_IDENTITY="new_staging",
    ).items()))
    backup.write_text("\n".join(f"{k}={v}" for k, v in sample().items()))
    assert gate.main([str(current), str(backup)]) == 0
    output = capsys.readouterr().out
    assert "MATCHES_CURRENT_STAGING_ID=FAIL" in output
    assert "AUTOMATIC_RESTORE=BLOCKED" in output
    assert "AUTHENTICATED_DB_OWNERSHIP=UNVERIFIED" in output
    assert "encoded%40password" not in output
    assert "staging_db" not in output

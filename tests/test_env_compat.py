import os

import pytest

from config.env_compat import Env


def test_boolean_and_list_environment_values(monkeypatch):
    monkeypatch.setenv("FEATURE_ENABLED", "yes")
    monkeypatch.setenv("HOSTS", "one.example, two.example,,")
    env = Env()
    assert env.bool("FEATURE_ENABLED") is True
    assert env.list("HOSTS") == ["one.example", "two.example"]


def test_database_url_parsing_for_sqlite_and_postgres():
    env = Env()
    sqlite = env.db("DATABASE_URL", default="sqlite:////srv/app/db.sqlite3")
    assert sqlite["ENGINE"] == "django.db.backends.sqlite3"
    assert sqlite["NAME"] == "/srv/app/db.sqlite3"

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://app_user:p%40ss@db.example:5432/zomorod?sslmode=require",
        )
        postgres = env.db("DATABASE_URL")
    finally:
        monkeypatch.undo()
    assert postgres["ENGINE"] == "django.db.backends.postgresql"
    assert postgres["NAME"] == "zomorod"
    assert postgres["USER"] == "app_user"
    assert postgres["PASSWORD"] == "p@ss"
    assert postgres["OPTIONS"] == {"sslmode": "require"}


def test_read_env_preserves_existing_process_values(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_COMPAT_TEST", "process-value")
    env_file = tmp_path / ".env"
    env_file.write_text(
        'ENV_COMPAT_TEST="file-value"\nNEW_ENV_COMPAT_TEST=from-file # comment\n',
        encoding="utf-8",
    )
    Env.read_env(env_file)
    assert os.environ["ENV_COMPAT_TEST"] == "process-value"
    assert os.environ["NEW_ENV_COMPAT_TEST"] == "from-file"
    monkeypatch.delenv("NEW_ENV_COMPAT_TEST")

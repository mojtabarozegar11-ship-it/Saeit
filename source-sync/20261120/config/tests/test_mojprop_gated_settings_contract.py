"""Static contract tests for staging-only database settings wiring."""

from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parents[1] / "settings.py"


def test_mojprop_settings_are_staging_gated_and_fail_closed():
    source = SETTINGS_PATH.read_text(encoding="utf-8")
    assert 'MPW_MOJPROP_DB_ALIAS_ENABLED", default=False' in source
    assert 'MPW_MOJPROP_DEPLOYMENT_ENV != "staging"' in source
    assert 'DATABASES["mojprop"] = environ.Env.db_url_config' in source
    assert 'DATABASE_ROUTERS = (' in source
    assert 'MPW_MOJPROP_DATABASE_URL", default=""' in source
    assert 'MPW_MOJPROP_IDENTITY_DIGEST_SECRET", default=""' in source
    assert 'MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS", default=""' in source
    assert 'env.db(_mojprop_database_url)' not in source


def test_factory_database_is_not_replaced_by_mojprop_alias():
    source = SETTINGS_PATH.read_text(encoding="utf-8")
    assert 'DATABASES = {' in source
    assert 'DATABASES["mojprop"] =' in source
    assert 'DATABASES["default"]' not in source.split('DATABASES["mojprop"] =', 1)[1]

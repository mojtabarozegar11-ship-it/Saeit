import pytest
from django.test import override_settings

from core.production_gate import ProductionGate


@pytest.mark.django_db
def test_production_settings_require_secret_and_hosts():
    with override_settings(DEBUG=False, SECRET_KEY="configured", ALLOWED_HOSTS=[]):
        result = ProductionGate().evaluate()
        assert not result.ready
        assert "ALLOWED_HOSTS is empty" in result.reasons

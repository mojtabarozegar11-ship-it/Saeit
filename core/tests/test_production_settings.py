import pytest
from django.test import override_settings


@pytest.mark.django_db
def test_production_settings_require_secret_and_hosts():
    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        with override_settings(DEBUG=False, SECRET_KEY="configured", ALLOWED_HOSTS=[]):
            from django.conf import settings
            assert settings.DEBUG is False

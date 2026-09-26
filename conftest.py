
import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def disable_ssl_redirect_for_all_pytest_django_tests():
    with override_settings(SECURE_SSL_REDIRECT=False):
        yield

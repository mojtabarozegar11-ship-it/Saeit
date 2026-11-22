# These are standalone CLI regression scripts requiring an explicit staged release
# directory. Their dedicated GitHub workflows execute them with the required
# positional argument. Collecting them via `pytest -q` passes "-q" as a stage
# path, causing unrelated global CI collection failures.
collect_ignore = [
    "scripts/test_zomorod_onepass_20261113.py",
    "scripts/test_zomorod_vision_ux_20261113.py",
]


import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def disable_ssl_redirect_for_all_pytest_django_tests():
    with override_settings(SECURE_SSL_REDIRECT=False):
        yield

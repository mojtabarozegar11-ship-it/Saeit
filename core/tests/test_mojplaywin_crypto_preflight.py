"""Release gate is fail-closed and never echoes secret or full wallet addresses."""
from unittest.mock import patch
import pytest
from django.test import override_settings
from core.management.commands.mojplaywin_crypto_preflight import read_only_check


def test_read_only_preflight_never_advertises_public_release():
    result = read_only_check()
    assert result["classification"] == "READ_ONLY_CONFIGURATION_CHECK"
    assert result["release_permitted"] is False
    assert result["isolated_deployment_verified"] is False
    assert result["off_host_backup_restore_tested"] is False
    assert result["live_transfer_tested"] is False
    assert result["no_wallet_secrets_or_addresses_printed"] is True


def test_preflight_insecure_settings_are_not_ready(tmp_path):
    with override_settings(
        DEBUG=True, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=["mojplaywin.com"],
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_TRX_ADDRESS="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(tmp_path),
        MOJPLAYWIN_ETH_CONFIRMATIONS=12, MOJPLAYWIN_TRX_CONFIRMATIONS=20,
    ):
        result = read_only_check()
        assert result["configuration_ready"] is False
        assert result["configuration_checks"]["private_files_outside_project"] is True
        assert result["configuration_checks"]["app_debug_disabled"] is False
        assert "eth.example.org" not in str(result)
        assert "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73" not in str(result)

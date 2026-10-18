"""Read-only, credential-redacted staging readiness inspection.

A green configuration check is NEVER proof of safe shared-host deployment,
off-host restore, wallet ownership, on-chain payment or legal compliance.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.mojplaywin_crypto_gateway import configured


def read_only_check():
    base = Path(settings.BASE_DIR).resolve()
    private_value = str(getattr(settings, "MOJPLAYWIN_PRIVATE_ASSET_ROOT", "") or "").strip()
    try:
        private_root = Path(private_value).resolve()
        folder_is_private = (
            bool(private_value) and Path(private_value).is_absolute()
            and private_root.is_dir()
            and not private_root.is_relative_to(base)
            and not base.is_relative_to(private_root)
        )
        static_value = str(getattr(settings, "STATIC_ROOT", "") or "")
        if static_value and private_root.is_relative_to(Path(static_value).resolve()):
            folder_is_private = False
    except (OSError, ValueError):
        folder_is_private = False
    rpc_value = str(getattr(settings, "MOJPLAYWIN_ETH_RPC_URL", "") or "")
    rpc = urlsplit(rpc_value)
    rpc_syntax = rpc.scheme == "https" and bool(rpc.hostname) and not rpc.username and not rpc.password
    checks = {
        "app_debug_disabled": not settings.DEBUG,
        "ssl_redirect_required": bool(settings.SECURE_SSL_REDIRECT),
        "session_cookie_secure": bool(settings.SESSION_COOKIE_SECURE),
        "csrf_cookie_secure": bool(settings.CSRF_COOKIE_SECURE),
        "mojplaywin_allowed_host": "mojplaywin.com" in settings.ALLOWED_HOSTS,
        "eth_public_address_and_https_rpc_configured": bool(configured("ETH") and rpc_syntax),
        "trx_public_address_valid": bool(configured("TRX")),
        "private_files_outside_project": bool(folder_is_private),
        "eth_confirmations_safe": isinstance(settings.MOJPLAYWIN_ETH_CONFIRMATIONS, int) and settings.MOJPLAYWIN_ETH_CONFIRMATIONS >= 12,
        "trx_confirmations_safe": isinstance(settings.MOJPLAYWIN_TRX_CONFIRMATIONS, int) and settings.MOJPLAYWIN_TRX_CONFIRMATIONS >= 20,
    }
    return {
        "scope": "mojplaywin.com native ETH and TRX only",
        "classification": "READ_ONLY_CONFIGURATION_CHECK",
        "configuration_checks": checks,
        "configuration_ready": all(checks.values()),
        "gateway_flag_enabled": bool(settings.MOJPLAYWIN_CRYPTO_ENABLED),
        "isolated_deployment_verified": False,
        "off_host_backup_restore_tested": False,
        "live_transfer_tested": False,
        "release_permitted": False,
        "no_wallet_secrets_or_addresses_printed": True,
    }


class Command(BaseCommand):
    help = "Read-only MojPlayWin crypto configuration and deployment blocking-gates check."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Exit nonzero unless config is complete.")

    def handle(self, *args, **options):
        results = read_only_check()
        self.stdout.write(json.dumps(results, sort_keys=True))
        if options.get("strict") and not results["configuration_ready"]:
            raise CommandError("Configuration incomplete; do not activate the gateway.")

"""CI-only guard: wallet proof preflight must precede any live schema migration.

Uses disposable SQLite test data. Never connects to cPanel, VPS or mainnet.
"""
import ast
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import DisallowedHost
from django.test import RequestFactory, TestCase, override_settings

from mpw_native_checkout.merchant_wallet_views import merchant_wallet_page


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mpw_activate_wallet_proof.py"


def read_preflight_code():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    activate = next(item for item in tree.body
                    if isinstance(item, ast.FunctionDef) and item.name == "activate")
    matches = [node.value.value for node in ast.walk(activate)
               if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name)
                       and target.id == "pre_migration_code" for target in node.targets)
               and isinstance(node.value, ast.Constant)
               and isinstance(node.value.value, str)]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one static pre-migration safety check")
    return source, matches[0]


class WalletProofPreMigrationGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="preflight-ci-only-owner",
            email="preflight-ci@example.invalid",
            password="nonproduction-fixture-only",
        )

    def test_preflight_code_compiles_and_migration_is_after_guard(self):
        source, snippet = read_preflight_code()
        compile(snippet, "<wallet-pre-migration-guard>", "exec")
        section = source.split("def activate():", 1)[1].split("\ndef main():", 1)[0]
        guard = section.index("pre_migration_code =")
        # Neither the supposedly isolated 'shadow' settings nor live settings
        # may issue a Django migration before the host and owner view check.
        self.assertNotIn('"migrate",PROOF_APP', section[:guard])
        self.assertIn('"migrate",PROOF_APP', section[guard:])

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
    def test_actual_guard_renders_owner_page_without_proof_table_reads(self):
        _, snippet = read_preflight_code()
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk):
            exec(compile(snippet, "<wallet-pre-migration-guard>", "exec"), {})
        self.assertEqual(
            self.owner.pk,
            get_user_model().objects.filter(is_superuser=True, is_active=True).get().pk,
        )

    @override_settings(ALLOWED_HOSTS=["localhost"])
    def test_actual_guard_rejects_disallowed_mojplaywin_host(self):
        _, snippet = read_preflight_code()
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk):
            with self.assertRaises(AssertionError):
                exec(compile(snippet, "<wallet-pre-migration-guard>", "exec"), {})

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
    def test_owner_view_rejects_wrong_owner_and_http(self):
        request = RequestFactory().get(
            "/merchant/wallet-proof/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        request.user = self.owner
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk + 1):
            self.assertEqual(merchant_wallet_page(request).status_code, 403)
        request = RequestFactory().get(
            "/merchant/wallet-proof/", secure=False, HTTP_HOST="mojplaywin.com"
        )
        request.user = self.owner
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk):
            self.assertEqual(merchant_wallet_page(request).status_code, 403)

    @override_settings(ALLOWED_HOSTS=["localhost"])
    def test_django_explicitly_rejects_unexpected_host(self):
        request = RequestFactory().get(
            "/merchant/wallet-proof/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        request.user = self.owner
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk):
            with self.assertRaises(DisallowedHost):
                merchant_wallet_page(request)

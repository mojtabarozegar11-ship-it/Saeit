"""Real source settings import and fail-closed native TRX configuration tests.

No Django app startup, database query, private-file read or sale activation.
"""
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / 'config/settings.py'
DOTENV_EXAMPLE = ROOT / '.env.example'
SALES = (
    'MPW_COMMERCE_RELEASE_READY',
    'MPW_COMMERCE_DOWNLOADS_ENABLED',
    'MPW_WALLETLESS_TRX_PUBLIC_ENABLED',
    'MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED',
    'MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED',
)


def configured(**overrides):
    variables = {
        'SECRET_KEY': 'synthetic-test-only-secret', 'DEBUG': 'False',
        'ALLOWED_HOSTS': 'mojplaywin.com',
    }
    variables.update(overrides)
    with patch.dict(os.environ, variables, clear=True):
        return runpy.run_path(str(SETTINGS))


class NativeTRXReleaseSettingsContract(unittest.TestCase):
    def test_no_sales_or_canary_or_private_root_are_implicitly_enabled(self):
        settings = configured()
        for flag in SALES:
            with self.subTest(flag=flag):
                self.assertIs(settings[flag], False)
        self.assertEqual(settings['MPW_TRX_PUBLIC_PRODUCT_IDS'], ())
        self.assertEqual(settings['MPW_COMMERCE_PRIVATE_ASSET_ROOT'], '')
        self.assertIs(settings['MPW_GUEST_RECOVERY_EMAIL_APPROVED'], False)

    def test_explicit_reviewed_sku_csv_is_sorted_and_deduplicated(self):
        settings = configured(MPW_TRX_PUBLIC_PRODUCT_IDS='879, 72,225, 72')
        self.assertEqual(settings['MPW_TRX_PUBLIC_PRODUCT_IDS'], (72, 225, 879))
        for flag in SALES:
            self.assertIs(settings[flag], False)

    def test_invalid_sku_list_is_empty_not_partially_approved(self):
        for raw in ('72,wrong,225', '72,,879', '-72,225', '0,225',
                    '72,True', '72, ۱۲۳', '9223372036854775808',
                    '9'*5000):
            with self.subTest(raw=raw[:60]):
                settings = configured(MPW_TRX_PUBLIC_PRODUCT_IDS=raw)
                self.assertEqual(settings['MPW_TRX_PUBLIC_PRODUCT_IDS'], ())

    def test_flags_are_only_true_when_explicitly_configured(self):
        settings = configured(MPW_COMMERCE_RELEASE_READY='True',
                              MPW_TRX_PUBLIC_PRODUCT_IDS='72')
        self.assertIs(settings['MPW_COMMERCE_RELEASE_READY'], True)
        self.assertIs(settings['MPW_WALLETLESS_TRX_PUBLIC_ENABLED'], False)
        self.assertIs(settings['MPW_COMMERCE_DOWNLOADS_ENABLED'], False)

    def test_private_root_setting_is_wired_without_creating_directory(self):
        settings = configured(MPW_COMMERCE_PRIVATE_ASSET_ROOT='/private-assets')
        self.assertEqual(settings['MPW_COMMERCE_PRIVATE_ASSET_ROOT'],
                         '/private-assets')
        self.assertIs(settings['MPW_WALLETLESS_TRX_PUBLIC_ENABLED'], False)

    def test_example_documents_all_gates_as_disabled(self):
        example = DOTENV_EXAMPLE.read_text('utf8')
        for flag in SALES:
            self.assertIn(flag + '=False', example)
        self.assertIn('MPW_TRX_PUBLIC_PRODUCT_IDS=\n', example)
        self.assertIn('MPW_COMMERCE_PRIVATE_ASSET_ROOT=\n', example)


if __name__ == '__main__':
    unittest.main()

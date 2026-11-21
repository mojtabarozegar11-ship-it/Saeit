"""Source contract tests for the current Zomorod store PHP — no network or writes."""
from pathlib import Path
import unittest

STORE = Path(__file__).resolve().parents[1] / "content/zomorod-v11/store_index.php"


class ExistingStoreMobileSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = STORE.read_text(encoding="utf-8")

    def test_existing_entrypoint_and_payment_hold_unchanged(self):
        for required in (
            "function storeEsc(string $x):string",
            "require_once $lib;",
            "zmStoreDb($private)",
            "FROM products WHERE enabled=1",
            "FROM free_digital_products WHERE enabled=1",
            "پرداخت آنلاین تا اتصال درگاه غیرفعال است.",
            "خرید آنلاین و برداشت وجه غیرفعال است.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_grid_never_requires_fixed_minimum_wider_than_phone(self):
        self.assertIn(
            "grid-template-columns:repeat(auto-fit,minmax(min(100%,255px),1fr))",
            self.source,
        )
        self.assertIn(".grid>article,.grid>section{min-width:0}", self.source)

    def test_long_sha_uses_scoped_block_wrap_not_page_clipping(self):
        self.assertIn(
            ".grid article small.muted{display:block;max-width:100%;"
            "overflow-wrap:anywhere;word-break:break-word}",
            self.source,
        )
        self.assertIn('<small class="muted">SHA-256: ', self.source)
        self.assertNotIn("overflow-x:hidden", self.source)

    def test_existing_template_structure_and_links_preserved(self):
        for token in (
            'lang="fa" dir="rtl"',
            'id="zm-specialty-stores"',
            'id="zm-company-official-contacts"',
            '/store/free-products/',
            '<div class="grid"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.source)

    def test_no_new_storefront_or_purchase_handler(self):
        self.assertEqual(self.source.count("function storeEsc("), 1)
        self.assertEqual(self.source.count("header('Cache-Control: public, max-age=60')"), 1)


if __name__ == "__main__":
    unittest.main()

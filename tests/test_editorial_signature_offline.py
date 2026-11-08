"""Attribution must be exact, final, and not duplicated on repeat cycles."""

import unittest

from core.editorial_signature import SIGNATURE, ensure_signed, has_final_signature


class EditorialSignatureTests(unittest.TestCase):
    def test_weather_and_news_body_signature(self):
        for body in ("گزارش هواشناسی", "متن خبر و منبع معتبر"):
            with self.subTest(body=body):
                signed = ensure_signed(body)
                self.assertEqual(signed, f"{body}\n\n{SIGNATURE}")
                self.assertTrue(has_final_signature(signed))

    def test_repeated_signing_is_idempotent(self):
        body = "خبر تحلیلی\n\n#مجتبی_روزگار\n"
        self.assertEqual(ensure_signed(ensure_signed(body)), body.rstrip())
        self.assertEqual(ensure_signed(body).count(SIGNATURE), 1)

    def test_signature_in_middle_is_not_final(self):
        body = "#مجتبی_روزگار\nمتن تازه"
        self.assertFalse(has_final_signature(body))
        self.assertTrue(ensure_signed(body).endswith("\n\n#مجتبی_روزگار"))

    def test_empty_body_has_signature_only(self):
        self.assertEqual(ensure_signed(None), SIGNATURE)


if __name__ == "__main__":
    unittest.main()

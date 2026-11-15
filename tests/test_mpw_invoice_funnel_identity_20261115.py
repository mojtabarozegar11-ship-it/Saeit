"""Offline regression for truthful invoice-created telemetry and product identity.

No Django import, network call, money transfer, mail, or customer database.
"""
import unittest
from types import SimpleNamespace

from services.mpw_invoice_funnel_identity import created_invoice_product_id as classify

GOOD = "/commerce/trx-easy/invoice/42/"


class Redirect:
    def __init__(self, location=GOOD, status=302):
        self.location, self.status_code = location, status

    def get(self, name, default=""):
        return self.location if name == "Location" else default


class InvoiceFunnelIdentityTests(unittest.TestCase):
    def check(self, response=None, args=(), kwargs=None):
        return classify(response if response is not None else Redirect(), args,
                        kwargs if kwargs is not None else {"product_id": 72})

    def test_01_keyword_product_id(self):
        self.assertEqual(self.check(), 72)

    def test_02_positional_product_id(self):
        self.assertEqual(self.check(args=(72,), kwargs={}), 72)

    def test_03_303_redirect(self):
        self.assertEqual(self.check(response=Redirect(status=303)), 72)

    def test_04_invoice_200_not_counted(self):
        self.assertIsNone(self.check(response=Redirect(status=200)))

    def test_05_301_redirect_not_counted(self):
        self.assertIsNone(self.check(response=Redirect(status=301)))

    def test_06_307_redirect_not_counted(self):
        self.assertIsNone(self.check(response=Redirect(status=307)))

    def test_07_boolean_status_not_counted(self):
        self.assertIsNone(self.check(response=Redirect(status=True)))

    def test_08_float_status_not_counted(self):
        self.assertIsNone(self.check(response=Redirect(status=302.0)))

    def test_09_absolute_other_origin_denied(self):
        self.assertIsNone(self.check(response=Redirect("https://attacker.invalid" + GOOD)))

    def test_10_scheme_relative_other_origin_denied(self):
        self.assertIsNone(self.check(response=Redirect("//attacker.invalid" + GOOD)))

    def test_11_wrong_local_path_denied(self):
        self.assertIsNone(self.check(response=Redirect("/store/")))

    def test_12_noninvoice_download_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/download/42/")))

    def test_13_missing_trailing_slash_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD[:-1])))

    def test_14_invoice_zero_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/invoice/0/")))

    def test_15_invoice_leading_zero_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/invoice/042/")))

    def test_16_negative_invoice_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/invoice/-42/")))

    def test_17_alphabetic_invoice_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/invoice/a42/")))

    def test_18_extra_path_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD + "status/")))

    def test_19_query_string_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD + "?next=https://attacker.invalid")))

    def test_20_fragment_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD + "#section")))

    def test_21_encoded_path_denied(self):
        self.assertIsNone(self.check(response=Redirect("/commerce/trx-easy/invoice/%34%32/")))

    def test_22_missing_location_denied(self):
        self.assertIsNone(self.check(response=Redirect("")))

    def test_23_nonstring_location_denied(self):
        self.assertIsNone(self.check(response=Redirect(42)))

    def test_24_unavailable_response_get_denied(self):
        self.assertIsNone(self.check(response=SimpleNamespace(status_code=302)))

    def test_25_malformed_url_denied(self):
        self.assertIsNone(self.check(response=Redirect("http://[malformed")))

    def test_26_oversize_location_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD + "x" * 300)))

    def test_27_product_zero_denied(self):
        self.assertIsNone(self.check(kwargs={"product_id": 0}))

    def test_28_negative_product_denied(self):
        self.assertIsNone(self.check(kwargs={"product_id": -5}))

    def test_29_bool_product_denied(self):
        self.assertIsNone(self.check(kwargs={"product_id": True}))

    def test_30_string_product_denied(self):
        self.assertIsNone(self.check(kwargs={"product_id": "72"}))

    def test_31_multiple_positional_values_denied(self):
        self.assertIsNone(self.check(args=(72, 73), kwargs={}))

    def test_32_mixed_positional_and_keyword_denied(self):
        self.assertIsNone(self.check(args=(72,), kwargs={"product_id": 72}))

    def test_33_extra_keyword_denied(self):
        self.assertIsNone(self.check(kwargs={"product_id": 72, "other": 73}))

    def test_34_unknown_keyword_denied(self):
        self.assertIsNone(self.check(kwargs={"invoice_id": 72}))

    def test_35_invalid_arg_container_denied(self):
        self.assertIsNone(self.check(args=[72], kwargs={}))

    def test_36_invalid_kwarg_container_denied(self):
        self.assertIsNone(classify(Redirect(), (), [72]))

    def test_37_empty_product_arguments_denied(self):
        self.assertIsNone(self.check(args=(), kwargs={}))

    def test_38_spaces_in_path_denied(self):
        self.assertIsNone(self.check(response=Redirect(GOOD + " ")))

    def test_39_path_with_double_slash_denied(self):
        self.assertIsNone(self.check(response=Redirect("//commerce/trx-easy/invoice/42/")))

    def test_40_product_identity_not_inferred_from_invoice_number(self):
        self.assertEqual(self.check(args=(879,), kwargs={}), 879)

    def test_41_large_valid_product_id(self):
        self.assertEqual(self.check(kwargs={"product_id": 2147483647}), 2147483647)


if __name__ == "__main__":
    unittest.main()

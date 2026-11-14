"""Offline buyer-email POST ambiguity tests for guest invoice creation.

Runs real AST-extracted _posted_email and _email source; substitutes only the
Django validator with a minimal shape stub for stdlib-only scoped CI. The
existing Django CI separately exercises full validate_email and Order writes.
No buyer PII, network, mail, DB connection, or monetary action.
"""
import ast
import importlib.util
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services/mpw_trx_email_recovery.py"
SOURCE_BYTES = SOURCE.read_bytes()


class FakeValidationError(Exception):
    pass


def fake_django_validate_email(value):
    if not isinstance(value, str) or value.count("@") != 1:
        raise FakeValidationError("invalid")
    name, domain = value.split("@")
    if not name or not domain or "." not in domain or " " in value:
        raise FakeValidationError("invalid")


tree = ast.parse(SOURCE_BYTES, filename=str(SOURCE))
functions = [node for node in tree.body
             if isinstance(node, ast.FunctionDef)
             and node.name in {"_email", "_posted_email"}]
assert {fn.name for fn in functions} == {"_email", "_posted_email"}
namespace = {
    "validate_email": fake_django_validate_email,
    "ValidationError": FakeValidationError,
}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"),
     namespace)
posted_email = namespace["_posted_email"]


class FakePost:
    def __init__(self, fields):
        self.fields = fields
        self.accessed = []

    def getlist(self, key):
        self.accessed.append(key)
        return self.fields.get(key, [])


def req(data=None, method="POST", *, fields=None):
    if fields is None:
        fields = {key: [value] for key, value in (data or {}).items()}
    return types.SimpleNamespace(method=method, POST=FakePost(fields))


class BuyerEmailPostContract(unittest.TestCase):
    def accepted(self, request, expected="buyer@example.com"):
        self.assertEqual(posted_email(request), expected)

    def rejected(self, request):
        with self.assertRaises(ValueError) as err:
            posted_email(request)
        self.assertNotIn("buyer@example.com", str(err.exception))
        self.assertNotIn("other@example.com", str(err.exception))

    def test_01_primary_email_accepted(self):
        self.accepted(req({"email": "buyer@example.com"}))

    def test_02_buyer_email_alias_accepted(self):
        self.accepted(req({"buyer_email": "buyer@example.com"}))

    def test_03_customer_email_alias_accepted(self):
        self.accepted(req({"customer_email": "buyer@example.com"}))

    def test_04_purchase_email_alias_accepted(self):
        self.accepted(req({"purchase_email": "buyer@example.com"}))

    def test_05_purchaser_email_alias_accepted(self):
        self.accepted(req({"purchaser_email": "buyer@example.com"}))

    def test_06_mixed_case_value_canonicalized(self):
        self.accepted(req({"email": "BUYER@EXAMPLE.COM"}))

    def test_07_surrounding_whitespace_trimmed(self):
        self.accepted(req({"email": "  buyer@example.com  "}))

    def test_08_missing_email_rejected(self):
        self.rejected(req({}))

    def test_09_get_method_cannot_issue_guest_email(self):
        self.rejected(req({"email": "buyer@example.com"}, method="GET"))

    def test_10_lowercase_post_method_rejected(self):
        self.rejected(req({"email": "buyer@example.com"}, method="post"))

    def test_11_missing_http_method_rejected(self):
        self.rejected(types.SimpleNamespace(POST=FakePost({"email":["buyer@example.com"]})))

    def test_12_missing_post_body_rejected(self):
        self.rejected(types.SimpleNamespace(method="POST"))

    def test_13_nonquerydict_post_body_rejected(self):
        self.rejected(types.SimpleNamespace(method="POST", POST={"email":"buyer@example.com"}))

    def test_14_duplicate_identical_email_fields_rejected(self):
        self.rejected(req(fields={"email":["buyer@example.com", "buyer@example.com"]}))

    def test_15_duplicate_conflicting_email_fields_rejected(self):
        self.rejected(req(fields={"email":["buyer@example.com", "other@example.com"]}))

    def test_16_duplicate_valid_plus_blank_rejected(self):
        self.rejected(req(fields={"email":["buyer@example.com", ""]}))

    def test_17_duplicate_blank_plus_valid_rejected(self):
        self.rejected(req(fields={"email":["", "buyer@example.com"]}))

    def test_18_two_aliases_identical_are_ambiguous(self):
        self.rejected(req({"email":"buyer@example.com", "buyer_email":"buyer@example.com"}))

    def test_19_two_aliases_conflicting_are_ambiguous(self):
        self.rejected(req({"email":"buyer@example.com", "buyer_email":"other@example.com"}))

    def test_20_blank_secondary_alias_cannot_be_silently_ignored(self):
        self.rejected(req(fields={"email":["buyer@example.com"], "buyer_email":[""]}))

    def test_21_blank_primary_with_valid_secondary_rejected(self):
        self.rejected(req(fields={"email":[""], "buyer_email":["buyer@example.com"]}))

    def test_22_three_distinct_aliases_rejected(self):
        self.rejected(req({"email":"buyer@example.com",
                           "buyer_email":"buyer@example.com",
                           "customer_email":"buyer@example.com"}))

    def test_23_noncollection_getlist_result_rejected(self):
        self.rejected(req(fields={"email":"buyer@example.com"}))

    def test_24_tuple_getlist_with_one_value_allowed(self):
        self.accepted(req(fields={"email":("buyer@example.com",)}))

    def test_25_tuple_getlist_with_two_values_rejected(self):
        self.rejected(req(fields={"email":("buyer@example.com", "buyer@example.com")}))

    def test_26_empty_tuple_means_no_buyer(self):
        self.rejected(req(fields={"email":()}))

    def test_27_integer_email_rejected(self):
        self.rejected(req(fields={"email":[123]}))

    def test_28_binary_email_rejected(self):
        self.rejected(req(fields={"email":[b"buyer@example.com"]}))

    def test_29_carriage_return_in_email_rejected(self):
        self.rejected(req({"email":"buyer@example.com\rInjected: header"}))

    def test_30_newline_in_email_rejected(self):
        self.rejected(req({"email":"buyer@example.com\nOther: value"}))

    def test_31_length_over_254_rejected(self):
        self.rejected(req({"email":"a"*247+"@example.com"}))

    def test_32_missing_at_sign_rejected(self):
        self.rejected(req({"email":"buyer.example.com"}))

    def test_33_space_only_email_rejected(self):
        self.rejected(req({"email":"    "}))

    def test_34_invalid_missing_domain_rejected(self):
        self.rejected(req({"email":"buyer@"}))

    def test_35_invalid_missing_local_part_rejected(self):
        self.rejected(req({"email":"@example.com"}))

    def test_36_many_duplicate_values_rejected_before_email_validation(self):
        self.rejected(req(fields={"email":["buyer@example.com"]*100}))

    def test_37_unknown_only_field_does_not_create_contact(self):
        self.rejected(req({"billing_contact":"buyer@example.com"}))

    def test_38_ignores_unrelated_product_and_csrf_fields(self):
        self.accepted(req({"email":"buyer@example.com",
                           "csrfmiddlewaretoken":"A"*64,
                           "product_id":"72"}))

    def test_39_server_reads_allowed_aliases_only(self):
        request = req({"email":"buyer@example.com"})
        self.accepted(request)
        self.assertEqual(request.POST.accessed, [
            "email", "buyer_email", "customer_email", "purchase_email",
            "purchaser_email"])

    def test_40_no_source_mutation_or_secret_echo(self):
        original = SOURCE.read_bytes()
        self.rejected(req(fields={"email":["buyer@example.com",
                                           "other@example.com"]}))
        self.assertEqual(SOURCE.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

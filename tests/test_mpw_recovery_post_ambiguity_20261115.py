"""Offline security regressions for exact recovery email/code POST parsing.

Executes the reviewed source helper AST, without Django, network, mail,
customer orders, payment, production database or private buyer information.
"""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_email_recovery.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
NODES = [
    node for node in TREE.body
    if (isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "_RECOVERY_EMAIL_ALIASES"
        for target in node.targets))
    or (isinstance(node, ast.FunctionDef)
        and node.name == "_exact_recovery_post_value")
]
if len(NODES) != 2:
    raise AssertionError("Exact source AST guard and alias contract must exist once")
SCOPE = {}
exec(compile(ast.Module(body=NODES, type_ignores=[]), str(SOURCE), "exec"), SCOPE)
guard = SCOPE["_exact_recovery_post_value"]


class Form:
    def __init__(self, **fields):
        self.fields = fields

    def getlist(self, key):
        return self.fields.get(key, [])


def req(*, method="POST", form=None, **fields):
    if form is None:
        form = Form(**fields)
    return SimpleNamespace(method=method, POST=form)


class RecoveryPostAmbiguityTests(unittest.TestCase):
    def read(self, request=None, field="email", length=254):
        if request is None:
            request = req(email=["Buyer@Example.com"])
        return guard(request, field, length)

    def rejected(self, request, field="email", length=254):
        with self.assertRaises(ValueError):
            self.read(request, field, length)

    def test_01_one_canonical_email(self):
        self.assertEqual(self.read(), "Buyer@Example.com")

    def test_02_one_canonical_code(self):
        self.assertEqual(self.read(req(code=["a" * 43]), "code", 43), "a" * 43)

    def test_03_get_request_denied(self):
        self.rejected(req(method="GET", email=["buyer@example.com"]))

    def test_04_delete_request_denied(self):
        self.rejected(req(method="DELETE", email=["buyer@example.com"]))

    def test_05_missing_request_method_denied(self):
        self.rejected(SimpleNamespace(POST=Form(email=["a@b.com"])))

    def test_06_missing_post_denied(self):
        self.rejected(SimpleNamespace(method="POST"))

    def test_07_nonquerydict_post_denied(self):
        self.rejected(req(form={"email": "a@b.com"}))

    def test_08_getlist_noncallable_denied(self):
        self.rejected(req(form=SimpleNamespace(getlist=None)))

    def test_09_missing_email_field_denied(self):
        self.rejected(req())

    def test_10_empty_email_list_denied(self):
        self.rejected(req(email=[]))

    def test_11_duplicate_identical_email_denied(self):
        self.rejected(req(email=["a@b.com", "a@b.com"]))

    def test_12_duplicate_different_email_denied(self):
        self.rejected(req(email=["a@b.com", "attacker@b.com"]))

    def test_13_empty_second_email_denied(self):
        self.rejected(req(email=["a@b.com", ""]))

    def test_14_blank_email_denied(self):
        self.rejected(req(email=[""]))

    def test_15_nonstring_email_denied(self):
        self.rejected(req(email=[42]))

    def test_16_nonstring_code_denied(self):
        self.rejected(req(code=[42]), "code", 43)

    def test_17_nested_email_array_denied(self):
        self.rejected(req(email=[["a@b.com"]]))

    def test_18_oversize_email_denied(self):
        self.rejected(req(email=["x" * 255]))

    def test_19_exact_max_email_length_remains_parseable(self):
        self.assertEqual(len(self.read(req(email=["x" * 254]))), 254)

    def test_20_email_tab_control_denied(self):
        self.rejected(req(email=["a@b.com\t"]))

    def test_21_email_newline_denied(self):
        self.rejected(req(email=["a@b.com\n"]))

    def test_22_email_carriage_return_denied(self):
        self.rejected(req(email=["a@b.com\r"]))

    def test_23_email_nul_denied(self):
        self.rejected(req(email=["a@b.com\x00"]))

    def test_24_email_del_denied(self):
        self.rejected(req(email=["a@b.com\x7f"]))

    def test_25_alias_buyer_email_denied(self):
        self.rejected(req(email=["a@b.com"], buyer_email=["b@b.com"]))

    def test_26_alias_customer_email_denied(self):
        self.rejected(req(email=["a@b.com"], customer_email=["b@b.com"]))

    def test_27_alias_purchase_email_denied(self):
        self.rejected(req(email=["a@b.com"], purchase_email=["b@b.com"]))

    def test_28_alias_purchaser_email_denied(self):
        self.rejected(req(email=["a@b.com"], purchaser_email=["b@b.com"]))

    def test_29_blank_extra_alias_denied(self):
        self.rejected(req(email=["a@b.com"], buyer_email=[""]))

    def test_30_duplicate_code_identical_denied(self):
        self.rejected(req(code=["a" * 43, "a" * 43]), "code", 43)

    def test_31_duplicate_code_conflicting_denied(self):
        self.rejected(req(code=["a" * 43, "b" * 43]), "code", 43)

    def test_32_missing_code_denied(self):
        self.rejected(req(), "code", 43)

    def test_33_code_too_long_denied(self):
        self.rejected(req(code=["a" * 44]), "code", 43)

    def test_34_code_with_newline_denied(self):
        self.rejected(req(code=["a" * 42 + "\n"]), "code", 43)

    def test_35_code_length_43_accepted_for_downstream_verifier(self):
        self.assertEqual(self.read(req(code=["z" * 43]), "code", 43), "z" * 43)

    def test_36_csrf_hidden_field_is_allowed(self):
        self.assertEqual(self.read(req(email=["a@b.com"], csrfmiddlewaretoken=["fake"])), "a@b.com")

    def test_37_tuple_single_value_allowed(self):
        self.assertEqual(self.read(req(email=("a@b.com",))), "a@b.com")

    def test_38_iterable_generator_rejected(self):
        self.rejected(req(email=(x for x in ["a@b.com"])))

    def test_39_string_getlist_result_rejected(self):
        self.rejected(req(email="a@b.com"))

    def test_40_no_get_shortcut_allowed(self):
        class MaliciousForm:
            def get(self, *args):
                raise AssertionError("QueryDict.get() bypass invoked")
            def getlist(self, field):
                return ["a@b.com"] if field == "email" else []
        self.assertEqual(self.read(req(form=MaliciousForm())), "a@b.com")

    def test_41_recovery_request_endpoint_calls_guard(self):
        endpoint = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                        and n.name == "recovery_request")
        self.assertTrue(any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "_exact_recovery_post_value"
            and any(isinstance(a, ast.Constant) and a.value == "email"
                    for a in node.args)
            for node in ast.walk(endpoint)
        ))

    def test_42_recovery_verify_endpoint_calls_guard(self):
        endpoint = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                        and n.name == "recovery_verify")
        self.assertTrue(any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "_exact_recovery_post_value"
            and any(isinstance(a, ast.Constant) and a.value == "code"
                    for a in node.args)
            for node in ast.walk(endpoint)
        ))

    def test_43_no_legacy_post_get_in_recovery_entrypoints(self):
        for name in ("recovery_request", "recovery_verify"):
            endpoint = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                            and n.name == name)
            self.assertFalse(any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "POST"
                for node in ast.walk(endpoint)
            ), name)


if __name__ == "__main__":
    unittest.main()

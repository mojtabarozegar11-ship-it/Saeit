"""Evidence, not production authority, for the current owner email order contract."""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_email_required_preflight_20261114.py"
spec = importlib.util.spec_from_file_location("mpw_email_required_preflight", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    temporary = tempfile.TemporaryDirectory()
    target = Path(temporary.name)
    for rel in m.SOURCES.values():
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, destination)
    return temporary, target


class EmailRequiredSourceContracts(unittest.TestCase):
    def test_01_all_real_reviewed_sources_pass_checks(self):
        result = m.inspect()
        self.assertTrue(result["source_candidate_complete"], [k for k,v in result["checks"].items() if not v])
        self.assertEqual(result["passed"], result["total"])
        self.assertGreaterEqual(result["total"], 30)

    def test_02_release_not_authorized_by_source(self):
        r = m.inspect()
        for key in ("effective_passenger_root_verified", "effective_checkout_template_verified",
                    "public_store_dynamic_verified", "checkout_security_headers_verified",
                    "real_guest_post_order_verified", "settled_payment_verified",
                    "paid_delivery_verified", "release_authorized"):
            self.assertFalse(r[key], key)
        self.assertIsNone(r["actual_collected_revenue"])

    def test_03_only_one_bot_identity(self):
        self.assertEqual(m.inspect()["canonical_bot"], "mojtaba.bot.ai")

    def test_04_source_parser_no_network_or_database(self):
        r = m.inspect()
        self.assertFalse(r["external_network_requests"])
        self.assertFalse(r["database_queries"])
        self.assertFalse(r["customer_data_read"])
        self.assertFalse(r["files_modified"])

    def test_05_file_missing_rejected(self):
        temp, root = fixture()
        with temp:
            (root / m.SOURCES["recovery"]).unlink()
            self.assertFalse(m.inspect(root)["source_candidate_complete"])

    def test_06_recovery_symlink_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["recovery"]
            path.unlink()
            path.symlink_to(ROOT / m.SOURCES["recovery"])
            self.assertFalse(m.inspect(root)["checks"]["recovery_source"])

    def test_07_ancestor_symlink_rejected(self):
        temp, root = fixture()
        with temp:
            guest = root / m.SOURCES["guest"]
            guest.unlink()
            (root/"services").rename(root/"symlinks")
            (root/"services").symlink_to(root/"symlinks", target_is_directory=True)
            self.assertFalse(m.inspect(root)["checks"]["guest_source"])

    def test_08_nested_duplicate_new_user_rejected(self):
        temp, root = fixture()
        with temp:
            guest = root / m.SOURCES["guest"]
            text = guest.read_text()
            text += "\ndef _new_user(request):\n    return None\n"
            guest.write_text(text)
            self.assertFalse(m.inspect(root)["checks"]["guest_constructor_unique"])

    def test_09_invalid_py_syntax_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text("def x(: bad")
            self.assertFalse(m.inspect(root)["checks"]["guest_source"])

    def test_10_non_utf8_source_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_bytes(b"\xff\xff")
            self.assertFalse(m.inspect(root)["checks"]["guest_source"])

    def test_11_empty_source_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text("")
            self.assertFalse(m.inspect(root)["checks"]["guest_source"])

    def test_12_missing_email_validator_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            text = path.read_text().replace("_posted_email(request)", "request.POST.get('email')")
            path.write_text(text)
            self.assertFalse(m.inspect(root)["checks"]["guest_validated_email_call"])

    def test_13_no_email_persist_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("user.email = submitted_email", "user.email = None"))
            self.assertFalse(m.inspect(root)["checks"]["guest_email_assignment"])

    def test_14_no_force_insert_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("user.save(force_insert=True)", "user.save()"))
            self.assertFalse(m.inspect(root)["checks"]["guest_account_force_insert"])

    def test_15_no_guest_password_lock_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("user.set_unusable_password()", "pass"))
            self.assertFalse(m.inspect(root)["checks"]["guest_unusable_password"])

    def test_16_privileged_guest_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("user.is_staff = False", "user.is_staff = True"))
            self.assertFalse(m.inspect(root)["checks"]["guest_staff_denied"])

    def test_17_unbound_checkout_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("return bound_checkout(", "return unchecked_checkout("))
            self.assertFalse(m.inspect(root)["checks"]["guest_order_bound_checkout_call"])

    def test_18_missing_render_guard_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("require_checkout_markup(response, product_id)",
                                                   "no_checkout_guard(response, product_id)"))
            self.assertFalse(m.inspect(root)["checks"]["guest_checkout_render_guard"])

    def test_19_recovery_checkout_without_claim_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["recovery"]
            path.write_text(path.read_text().replace("GuestOrderEmail.objects.create(", "Other.objects.create("))
            self.assertFalse(m.inspect(root)["checks"]["recovery_order_claim_creation"])

    def test_20_recovery_without_atomic_order_binding_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["recovery"]
            path.write_text(path.read_text().replace("with transaction.atomic():",
                                                   "with custom_context():"))
            self.assertFalse(m.inspect(root)["checks"]["recovery_order_transaction"])

    def test_21_recovery_without_financial_finality_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["recovery"]
            path.write_text(path.read_text().replace(
                "verified_walletless_credit(order, intent)", "invoice_is_paid(order, intent)"))
            self.assertFalse(m.inspect(root)["checks"]["recovery_finality_on_access"])

    def test_22_recovery_without_delivery_readiness_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["recovery"]
            path.write_text(path.read_text().replace("not _ready(order)", "False"))
            self.assertFalse(m.inspect(root)["checks"]["recovery_delivery_guard"])

    def test_23_missing_model_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["claims"]
            path.write_text(path.read_text().replace("class GuestOrderEmail", "class Unrelated"))
            self.assertFalse(m.inspect(root)["checks"]["claim_model_trio"])

    def test_24_missing_migration_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["migration"]
            path.write_text(path.read_text().replace('name="GuestOrderEmail"', 'name="OtherOrder"'))
            self.assertFalse(m.inspect(root)["checks"]["migration_model_trio"])

    def test_25_missing_model_import_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["registration"]
            path.write_text(path.read_text().replace(
                "from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate", "pass"))
            self.assertFalse(m.inspect(root)["checks"]["registered_claim_model"])

    def test_26_missing_checkout_contract_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["render"]
            path.write_text(path.read_text().replace("def require_checkout_markup(", "def old_checkout_markup("))
            self.assertFalse(m.inspect(root)["checks"]["render_contract_function"])

    def test_27_missing_cookie_secure_flag_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("secure=True, httponly=True", "secure=False, httponly=True"))
            self.assertFalse(m.inspect(root)["checks"]["guest_cookie_secure"])

    def test_28_missing_cookie_httponly_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text(path.read_text().replace("secure=True, httponly=True", "secure=True, httponly=False"))
            self.assertFalse(m.inspect(root)["checks"]["guest_cookie_httponly"])

    def test_29_no_success_claim_without_runtime(self):
        r = m.require_source()
        self.assertTrue(r["must_still_verify_applied_migration"])
        self.assertFalse(r["release_authorized"])

    def test_30_cli_source_report_only(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        prefix = "MPW_EMAIL_REQUIRED_SOURCE="
        self.assertTrue(proc.stdout.startswith(prefix))
        report = json.loads(proc.stdout[len(prefix):])
        self.assertTrue(report["source_candidate_complete"])
        self.assertFalse(report["paid_delivery_verified"])

    def test_31_oversize_source_rejected(self):
        temp, root = fixture()
        with temp:
            path = root / m.SOURCES["guest"]
            path.write_text("x" * (m.MAX_BYTES + 1))
            self.assertFalse(m.inspect(root)["checks"]["guest_source"])

    def test_32_source_only_no_customer_contents_exposed(self):
        result = json.dumps(m.inspect())
        self.assertNotIn("SECRET_KEY=", result)
        self.assertNotIn("@gmail.com", result)
        self.assertNotIn("customer_email", result)


if __name__ == "__main__":
    unittest.main()

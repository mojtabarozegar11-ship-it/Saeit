"""No-payment, no-database regression for the guarded live TRX rights gate."""
import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/mpw_trx_rights_live_guard_20261028.py"
spec=importlib.util.spec_from_file_location("rights_guard",SCRIPT)
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

def fixture():
    context="def checkout_flags(request):\n"+guard.CONTEXT_OLD
    web=(guard.WEB_IMPORT_OLD+"\n"
         "def _select_order(product_id, buyer_id, connection):\n"
         "    with transaction.atomic(using=connection.alias):\n"
         "        product=Product.objects.select_for_update().get(pk=product_id)\n"
         +guard.WEB_CHECK_OLD+
         "            raise PaymentHold('not eligible')\n")
    pages=(guard.PAGES_IMPORT_OLD+"\n"
           "def public_shop(request):\n"
           "    for p in products:\n"
           +guard.PAGES_CATALOG_OLD+
           "        pass\n\n"
           "def product_checkout(request, product_id):\n"
           "    product=get_product(product_id)\n"
           +guard.PAGES_CHECKOUT_OLD+
           "    return product\n")
    return {"context":context,"web":web,"pages":pages}

class GuardTests(unittest.TestCase):
    def test_exact_edits_are_idempotent_and_compilable(self):
        patched={}
        for key,src in fixture().items():
            with self.subTest(key=key):
                new,changed=guard.transform(key,src)
                self.assertTrue(changed)
                self.assertNotEqual(new,src)
                self.assertEqual(guard.transform(key,new),(new,False))
                compile(new,key,"exec")
                patched[key]=new
        guard.check_structure(patched)

    def test_catalog_stays_visible_while_new_checkout_is_guarded(self):
        """Rights clearance must not remove the three existing public listings."""
        original=fixture()["pages"]
        patched,changed=guard.transform("pages",original)
        self.assertTrue(changed)
        original_shop=original.split("def public_shop(request):",1)[1].split(
            "def product_checkout(request, product_id):",1)[0]
        patched_shop=patched.split("def public_shop(request):",1)[1].split(
            "def product_checkout(request, product_id):",1)[0]
        self.assertEqual(original_shop,patched_shop)
        self.assertIn(guard.PAGES_CATALOG_OLD,patched_shop)
        self.assertNotIn("rights_cleared_for_sale(p)",patched_shop)
        self.assertIn("rights_cleared_for_sale(product)",patched)
        guard.check_structure({"pages":patched})

    def test_catalog_hiding_patch_is_rejected(self):
        original=fixture()["pages"]
        patched,_=guard.transform("pages",original)
        hidden=patched.replace(guard.PAGES_CATALOG_OLD,
            "        if not _eligible(p) or not rights_cleared_for_sale(p): continue\n")
        with self.assertRaisesRegex(RuntimeError,"PUBLIC_CATALOG_VISIBILITY_CHANGED"):
            guard.check_structure({"pages":hidden})

    def test_ambiguous_or_missing_anchor_fails_closed(self):
        for key,src in fixture().items():
            anchor=guard.PATCHES[key][0][0]
            for corrupted in (src.replace(anchor,"",1),src+anchor):
                with self.subTest(key=key):
                    with self.assertRaises(RuntimeError):
                        guard.transform(key,corrupted)

    def test_partial_module_is_refused(self):
        src=fixture()["web"].replace(guard.WEB_IMPORT_OLD,guard.WEB_IMPORT_NEW,1)
        with self.assertRaisesRegex(RuntimeError,"PARTIAL_MODULE_PATCH"):
            guard.transform("web",src)

    def test_private_backup_idempotent_apply_verify_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            with patch.object(guard,"TARGETS",paths),\
                 patch.object(guard,"BACKUPS",root/"private"),\
                 patch.object(guard,"guard"),\
                 patch.object(guard,"runtime_validate"),\
                 patch.object(guard,"restart") as restart:
                guard.operation("check")
                self.assertFalse((root/"private").exists())
                guard.operation("apply","202610280001")
                self.assertEqual(restart.call_count,1)
                guard.operation("verify","202610280001")
                guard.operation("apply","202610280002")
                self.assertEqual(restart.call_count,1)
                self.assertFalse((root/"private"/"202610280002").exists())
                guard.operation("rollback","202610280001")
                self.assertEqual(restart.call_count,2)
                for k,path in paths.items():
                    self.assertEqual(path.read_text("utf8"),fixture()[k])

    def test_rollback_never_overwrites_newer_edit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            with patch.object(guard,"TARGETS",paths),\
                 patch.object(guard,"BACKUPS",root/"private"),\
                 patch.object(guard,"guard"),\
                 patch.object(guard,"runtime_validate"),\
                 patch.object(guard,"restart"):
                guard.operation("apply","202610280003")
                paths["web"].write_text(paths["web"].read_text("utf8")+"\n# later edit\n")
                with self.assertRaisesRegex(RuntimeError,"NEWER_SOURCE_EDIT"):
                    guard.operation("rollback","202610280003")

    def test_recover_interrupted_partial_install_and_is_idempotent(self):
        """A timed-out remote apply may have written only some modules."""
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            with patch.object(guard,"TARGETS",paths),\
                 patch.object(guard,"BACKUPS",root/"private"),\
                 patch.object(guard,"guard"),\
                 patch.object(guard,"runtime_validate"),\
                 patch.object(guard,"restart") as restart:
                guard.operation("apply","202610280004")
                # Simulate an interrupted multi-file write: only one file new.
                paths["web"].write_text(fixture()["web"],encoding="utf8")
                paths["pages"].write_text(fixture()["pages"],encoding="utf8")
                restart.reset_mock()
                guard.operation("recover","202610280004")
                self.assertEqual(restart.call_count,1)
                for k,path in paths.items():
                    self.assertEqual(path.read_text("utf8"),fixture()[k])
                guard.operation("recover","202610280004")
                self.assertEqual(restart.call_count,1)

    def test_recover_refuses_newer_edits_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            with patch.object(guard,"TARGETS",paths),\
                 patch.object(guard,"BACKUPS",root/"private"),\
                 patch.object(guard,"guard"),\
                 patch.object(guard,"runtime_validate"),\
                 patch.object(guard,"restart") as restart:
                guard.operation("apply","202610280005")
                paths["web"].write_text(paths["web"].read_text("utf8")+"\n# concurrent edit\n",encoding="utf8")
                before={k:path.read_bytes() for k,path in paths.items()}
                restart.reset_mock()
                with self.assertRaisesRegex(RuntimeError,"NEWER_SOURCE_EDIT"):
                    guard.operation("recover","202610280005")
                self.assertEqual(before,{k:path.read_bytes() for k,path in paths.items()})
                restart.assert_not_called()


    def test_runtime_receipt_rejects_missing_required_sku(self):
        def receipt(missing=None):
            products={str(sku):{"exists":sku!=missing,"explicit_rights":False}
                      for sku in (72,225,879)}
            return "MPW_TRX_RIGHTS_RUNTIME="+json.dumps({"products":products})+"\\n"
        for missing in (72,225,879):
            with self.subTest(missing=missing), patch.object(
                guard.subprocess,"run",
                return_value=SimpleNamespace(returncode=0,stdout=receipt(missing),
                                             stderr="")):
                with self.assertRaisesRegex(RuntimeError,"RIGHTS_REQUIRED_PRODUCT_MISSING"):
                    guard.runtime_validate()
        with patch.object(guard.subprocess,"run",
                          return_value=SimpleNamespace(returncode=0,stdout=receipt(),
                                                       stderr="")):
            guard.runtime_validate()

    def test_directory_durability_failure_aborts_before_source_edits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            original={k:p.read_bytes() for k,p in paths.items()}
            with patch.object(guard,"TARGETS",paths),\\
                 patch.object(guard,"BACKUPS",root/"private"),\\
                 patch.object(guard,"guard"),\\
                 patch.object(guard,"runtime_validate"),\\
                 patch.object(guard,"restart") as restart,\\
                 patch.object(guard.os,"open",side_effect=OSError("directory sync denied")):
                with self.assertRaisesRegex(OSError,"directory sync denied"):
                    guard.operation("apply","202610280011")
            self.assertEqual(original,{k:p.read_bytes() for k,p in paths.items()})
            restart.assert_not_called()

    def test_atomic_rejects_stale_source_without_overwriting(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"module.py"
            path.write_bytes(b"newer external source")
            with self.assertRaisesRegex(RuntimeError,"CONCURRENT_EDIT_BEFORE_REPLACE"):
                guard.atomic(path,b"old release",expected=guard.digest(b"expected source"))
            self.assertEqual(path.read_bytes(),b"newer external source")

    def test_apply_detects_edit_between_preflight_and_replace(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={k:root/(k+".py") for k in fixture()}
            for k,path in paths.items():
                path.write_text(fixture()[k],encoding="utf8")
            original_atomic=guard.atomic
            def concurrent_edit(path,raw,expected=None):
                if path==paths["context"]:
                    path.write_text(path.read_text("utf8")+"\n# another agent edit\n",encoding="utf8")
                return original_atomic(path,raw,expected)
            with patch.object(guard,"TARGETS",paths),\
                 patch.object(guard,"BACKUPS",root/"private"),\
                 patch.object(guard,"guard"),\
                 patch.object(guard,"runtime_validate"),\
                 patch.object(guard,"restart") as restart,\
                 patch.object(guard,"atomic",side_effect=concurrent_edit):
                with self.assertRaisesRegex(RuntimeError,"CONCURRENT_EDIT_BEFORE_REPLACE"):
                    guard.operation("apply","202610280006")
                self.assertIn("# another agent edit",paths["context"].read_text("utf8"))
                for key in ("web","pages"):
                    self.assertEqual(paths[key].read_text("utf8"),fixture()[key])
                restart.assert_not_called()

if __name__=="__main__":
    unittest.main()

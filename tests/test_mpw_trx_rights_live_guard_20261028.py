"""No-payment, no-database regression for the guarded live TRX rights gate."""
import importlib.util
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

if __name__=="__main__":
    unittest.main()

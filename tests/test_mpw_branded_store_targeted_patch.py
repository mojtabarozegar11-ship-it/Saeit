"""Targeted patch tests: any unexpected production source must be rejected."""
import ast
import unittest

from scripts.mpw_branded_store_targeted_patch import (
    EXPECTED, REPLACEMENT, prepare,
)


class BrandStorePatchSafetyTests(unittest.TestCase):
    def setUp(self):
        self.prefix=(
            'from django.http import Http404\n'
            'from django.shortcuts import render\n'
            'from core.brand import brand_for_request\n'
            'from core.models import Product\n\n'
            'def unrelated_brand_view(request):\n'
            '    return "keep the rest unchanged"\n\n'
        )
        self.suffix=(
            '\ndef another_live_route(request):\n'
            '    return "preserve website"\n'
        )

    def test_exact_active_function_is_only_change(self):
        original=self.prefix+EXPECTED+self.suffix
        result,changed=prepare(original)
        self.assertEqual(changed,1)
        self.assertTrue(result.startswith(self.prefix))
        self.assertTrue(result.endswith(self.suffix))
        self.assertEqual(result.count("def branded_store(request):"),1)
        self.assertEqual(result.count("mpw_verified_factory_cards.html"),1)
        self.assertIn('render(request,"brands/mojplaywin/store.html",context)',result)
        self.assertIn("if marker in raw and raw.count(marker)==1:",result)
        self.assertNotIn("factory_publication_permission = True",result)
        compile(result,"brand_views.py","exec")

    def test_unknown_view_edit_blocks_patch(self):
        code=self.prefix+EXPECTED.replace('order_by("-id")','order_by("id")')+self.suffix
        with self.assertRaisesRegex(ValueError,"DIFFERS_FROM_VERIFIED_BASELINE"):
            prepare(code)

    def test_wrong_brand_blocks_patch(self):
        code=self.prefix+EXPECTED.replace('brand.code!="mojplaywin"','brand.code!="zomorodmelal"')+self.suffix
        with self.assertRaises(ValueError):
            prepare(code)

    def test_custom_existing_extensions_not_overwritten(self):
        code=self.prefix+EXPECTED.replace('return render(request,','audit_record(request)\n    return render(request,')+self.suffix
        with self.assertRaises(ValueError):
            prepare(code)

    def test_never_overwrite_preinstalled_patch(self):
        with self.assertRaises(ValueError):
            prepare(self.prefix+REPLACEMENT+self.suffix)

    def test_no_or_multiple_views_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.prefix+self.suffix)
        with self.assertRaises(ValueError):
            prepare(self.prefix+EXPECTED+"\n"+EXPECTED)

    def test_no_payment_or_database_writes_in_patched_function(self):
        result,_=prepare(self.prefix+EXPECTED+self.suffix)
        ast.parse(result)
        region=result.split("def branded_store(request):",1)[1].split("def another_live_route(",1)[0]
        for forbidden in (".save(", ".delete(", "ApprovalService", ".create(", "checkout(", "PaymentIntent(", "migrate", "subprocess"):
            self.assertNotIn(forbidden,region)
        self.assertIn("return response",region)

    def test_extra_non_target_function_remains_unchanged(self):
        original=self.prefix+EXPECTED+self.suffix
        changed,_=prepare(original)
        self.assertEqual(changed.split("def unrelated_brand_view")[1].split("def branded_store")[0],
                         original.split("def unrelated_brand_view")[1].split("def branded_store")[0])


if __name__=="__main__":
    unittest.main()

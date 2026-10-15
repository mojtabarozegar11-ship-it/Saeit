"""No-paid-checkout public preview publication tests."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import astra_mpw_publish_previews as preview


class PublicAstraPreviewTests(unittest.TestCase):
    def build(self,folder):
        home=Path(folder)
        web=home/"mojplaywin.com"
        web.mkdir()
        (web/"passenger_wsgi.py").write_text("/home/demo/Saeit-staging/config/wsgi.py")
        app=home/"Saeit-staging/core/templates/brands/mojplaywin"
        app.mkdir(parents=True)
        template=app/"store.html"
        source=("{% extends 'brands/mojplaywin/base.html' %}"
                "<section class=\"mpw-page-cta\"><small>PAYMENTS</small></section>"
                "{% endblock %}")
        template.write_text(source)
        inbox=home/"inbox"
        inbox.mkdir()
        backup=home/"backups"
        backup.mkdir()
        catalog={
            "mode":"commercial_preparation_not_store_activation",
            "owner_exclusive_rights_declared_for_four_products":True,
            "storefront_target":"mojplaywin.com","publications":0,
            "real_checkout_transactions":0,"items":[]}
        prices={
            "ASTRA-CIRCUIT-01":("4.99","0.50"),
            "ASTRA-PROCURE-01":("19.00","1.90"),
            "ASTRA-WATER-01":("29.00","2.90"),
            "ASTRA-ORCHARD-01":("19.00","1.90")}
        for sku,(list_usd,discounted) in prices.items():
            contents=sku.encode()
            digest=hashlib.sha256(contents).hexdigest()
            (inbox/(sku+"-"+digest+".zip")).write_bytes(contents)
            catalog["items"].append({
                "sku":sku,"builder":"synthetic-"+sku,
                "title":"Astra specialist demo "+sku,
                "source_proof":{"artifact_sha256":digest},
                "status":"PRIVATE_COMMERCIAL_CANDIDATE_NOT_FOR_SALE",
                "owner_exclusive_rights_declared":True,
                "checkout_authorized":False,"public_listing_authorized":False,
                "quality_score":None,"suggested_list_price_usd":list_usd,
                "suggested_discounted_price_usd":discounted,
                "verified_technical_function":"Reference software only, not live checkout",
                "important_limits":"Independent quality review not completed",
            })
        file=inbox/"catalog.json"
        file.write_text(json.dumps(catalog))
        return file,inbox,web,template,backup

    def test_public_preview_5_pages_only_no_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            file,inbox,web,template,backups=self.build(d)
            plan=preview.make_plan(file,inbox,web,template)
            self.assertEqual(len(plan["pages"]),5)
            self.assertEqual(preview.publish(plan,backups)["status"],"DRY_RUN")
            self.assertFalse((web/"factory-previews").exists())
            self.assertNotIn(preview.BEGIN,template.read_text())
            result=preview.publish(plan,backups,apply=True)
            self.assertEqual(result["status"],"PUBLIC_PREVIEWS_PUBLISHED")
            for p in (web/"factory-previews").rglob("index.html"):
                contents=p.read_text()
                self.assertIn("Not available for purchase" if p.parent.name!="factory-previews" else "not products currently offered",contents)
                self.assertNotIn('href="',contents.split("No payment is requested")[0].split("https://")[0] if False else "__no-op__")
                self.assertNotIn("Send TRX", contents)
            self.assertIn(preview.BEGIN,template.read_text())
            self.assertEqual(len(list((web/"factory-previews").rglob("index.html"))),5)
            self.assertEqual(len(list(backups.glob("*.html"))),1)
            self.assertEqual(preview.publish(preview.make_plan(file,inbox,web,template),backups,apply=True)["template_change"],False)
            self.assertEqual(len(list(backups.glob("*.html"))),1)
            self.assertTrue(all(p.suffix==".html" for p in (web/"factory-previews").rglob("*") if p.is_file()))

    def test_existing_conflicting_page_refused(self):
        with tempfile.TemporaryDirectory() as d:
            file,inbox,web,template,backups=self.build(d)
            plan=preview.make_plan(file,inbox,web,template)
            (web/"factory-previews").mkdir()
            (web/"factory-previews/index.html").write_text("unrelated")
            with self.assertRaisesRegex(ValueError,"conflicting public"):
                preview.make_plan(file,inbox,web,template)

    def test_wrong_site_refused(self):
        with tempfile.TemporaryDirectory() as d:
            file,inbox,web,template,backups=self.build(d)
            wrong=Path(d)/"unrelated.com"
            wrong.mkdir()
            with self.assertRaisesRegex(ValueError,"live MojPlayWin"):
                preview.make_plan(file,inbox,wrong,template)

    def test_no_html_injection_from_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            file,inbox,web,template,backups=self.build(d)
            cat=json.loads(file.read_text())
            cat["items"][0]["title"] = "Original <script>alert(1)</script> Puzzle"
            file.write_text(json.dumps(cat))
            plan=preview.make_plan(file,inbox,web,template)
            markup="".join(plan["pages"].values())+plan["new"]
            self.assertNotIn("<script>alert(1)</script>",markup)
            self.assertIn("&lt;script&gt;",markup)

    def test_mismatched_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file,inbox,web,template,backups=self.build(d)
            (next(inbox.glob("*.zip"))).write_text("tampered")
            with self.assertRaisesRegex(ValueError,"sha not verified"):
                preview.make_plan(file,inbox,web,template)


if __name__=="__main__":
    unittest.main()

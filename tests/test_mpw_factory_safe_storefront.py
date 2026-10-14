"""MojPlayWin-only safe store presentation. No production write or payment."""
from decimal import Decimal
from django.test import TestCase
from core.models import Product
from core.factory_storefront import factory_card

FREE="/factory-releases/farm-enterprise-economics-v1/Farm_Enterprise_Economics_Toolkit_Free_v1.zip"


def farm_meta():
    return {
        "factory_origin":"saeit_vps","factory_recipe":"farm_enterprise_economics",
        "factory_software_qa":"passed","factory_publication_permission":True,
        "factory_commercial_status":"published_free_download_no_checkout",
        "factory_public_download_url":FREE,
    }


def water_meta():
    return {
        "factory_origin":"saeit_vps","factory_recipe":"water_budget_economics",
        "factory_software_qa":"passed","factory_publication_permission":True,
        "factory_paid_checkout_ready":False,"factory_payment_mainnet_verified":False,
        "factory_fulfillment_production_verified":False,
        "factory_license_review":"pending","factory_support_review":"pending",
        "factory_assessed_reference_usd":"9.90",
        "factory_launch_reduction_percent":"90",
        "factory_verified_checkout_url":"/checkout/verified-water/",
    }


class FactoryStorefrontTests(TestCase):
    def create(self,title,price,active,metadata):
        return Product.objects.create(
            title=title,price=Decimal(price),currency="USD",active=active,
            product_type="digital",metadata=metadata
        )

    def store(self,host="mojplaywin.com"):
        return self.client.get("/store/",HTTP_HOST=host)

    def test_inactive_factory_products_invisible_even_when_priced(self):
        self.create("Private farm", "0.00",False,farm_meta())
        self.create("Water Budget $0.99", "0.99",False,water_meta())
        response=self.store()
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,"Private farm")
        self.assertNotContains(response,"Water Budget $0.99")
        self.assertNotContains(response,"Proceed to secure checkout")

    def test_only_approved_free_product_shows_accurate_download(self):
        p=self.create("Free farm toolkit","0.00",True,farm_meta())
        response=self.store()
        self.assertContains(response,"Free farm toolkit")
        self.assertContains(response,"/factory-releases/farm-enterprise-economics-v1/")
        self.assertContains(response,"Free download")
        self.assertNotContains(response,"90% below")
        self.assertNotContains(response,"Proceed to secure checkout")
        self.assertEqual(factory_card(p)["price"],"Free")

    def test_approvals_are_enforced_even_if_flag_active(self):
        meta=farm_meta()
        meta["factory_publication_permission"]=False
        self.create("Unapproved free","0.00",True,meta)
        self.assertNotContains(self.store(),"Unapproved free")
        meta=farm_meta()
        meta["factory_public_download_url"]="https://fake.example/private.zip"
        self.create("Unsafe link","0.00",True,meta)
        self.assertNotContains(self.store(),"Unsafe link")

    def test_paid_inactive_or_unverified_cannot_offer_buy_button(self):
        self.create("Water after valuation","0.99",True,water_meta())
        response=self.store()
        self.assertNotContains(response,"Water after valuation")
        self.assertNotContains(response,"Proceed to secure checkout")

    def test_verified_paid_sample_requires_checkout_fulfillment_and_license(self):
        flags=water_meta()
        flags.update({
            "factory_paid_checkout_ready":True,
            "factory_payment_mainnet_verified":True,
            "factory_fulfillment_production_verified":True,
            "factory_license_review":"verified",
            "factory_support_review":"verified",
        })
        p=self.create("Checked paid product","0.99",True,flags)
        response=self.store()
        self.assertContains(response,"Checked paid product")
        self.assertContains(response,"USD $0.99")
        self.assertContains(response,"/checkout/verified-water/")
        self.assertContains(response,"90% below assessed launch valuation")
        self.assertContains(response,"not a former sale price")
        self.assertNotContains(response,"<del")
        self.assertEqual(factory_card(p)["kind"],"paid")

    def test_checkout_url_injection_rejected(self):
        flags=water_meta()
        flags.update({
            "factory_paid_checkout_ready":True,
            "factory_payment_mainnet_verified":True,
            "factory_fulfillment_production_verified":True,
            "factory_license_review":"verified",
            "factory_support_review":"verified",
            "factory_verified_checkout_url":"//malicious.invalid/checkout/",
        })
        self.create("Unsafe payment link","0.99",True,flags)
        self.assertNotContains(self.store(),"Unsafe payment link")

    def test_discount_value_mismatch_blocks_promotion(self):
        flags=water_meta()
        flags.update({
            "factory_paid_checkout_ready":True,
            "factory_payment_mainnet_verified":True,
            "factory_fulfillment_production_verified":True,
            "factory_license_review":"verified",
            "factory_support_review":"verified",
            "factory_assessed_reference_usd":"99.90",
        })
        self.create("Wrong reference","0.99",True,flags)
        self.assertNotContains(self.store(),"Wrong reference")

    def test_other_site_keeps_its_existing_template_and_active_catalog(self):
        self.create("Ordinary product","5.00",True,{})
        result=self.store("zomorodmelal.ir")
        self.assertEqual(result.status_code,200)
        self.assertContains(result,"Ordinary product")
        self.assertNotContains(result,"Smart tools. Clear value.")

    def test_nonfactory_products_do_not_disappear_from_mojplaywin(self):
        self.create("Independent partner course","9.00",True,{})
        self.assertContains(self.store(),"Independent partner course")

    def test_real_branded_route_context_scoped_to_mojplaywin(self):
        from types import SimpleNamespace
        from core.brand_store_integration import safe_brand_store_context
        from core.factory_storefront import presentation
        product=self.create("Approved free", "0.00", True, farm_meta())
        context=safe_brand_store_context(SimpleNamespace(code="mojplaywin"), [product])
        self.assertEqual(len(context["factory_cards"]),1)
        self.assertEqual(context["products"],[])
        with self.assertRaises(ValueError):
            safe_brand_store_context(SimpleNamespace(code="zomorodmelal"), [product])

"""Cross-contract between existing income services and the one-bot portfolio."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def imported(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class SalesSourceCrossContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.offers=imported("revenue_dual_offer_qualifier.py","two_offers_cross_contract")
        cls.port=imported("mojtaba_revenue_portfolio.py","revenue_portfolio_cross_contract")

    def test_draft_catalogue_exactly_matches_existing_service_offers(self):
        codes={x["code"] for x in self.port.catalogue()["items"]
               if x["source_status"]=="draft_inquiry_source"}
        self.assertEqual(codes, set(self.offers.OFFERS))

    def test_each_source_offer_still_uses_one_canonical_bot(self):
        for offer,pack in (("website_checkout_repair","diagnosis"),
                           ("farm_break_even","analysis")):
            entry={"offer":offer,"package":pack,"scope_items":1,"evidence_items":1,
                   "consent_to_contact":True,"inputs_available":True,"synthetic_example":True}
            got=self.offers.qualify(entry)
            self.assertEqual(got["canonical_bot"],self.port.BOT)
            self.assertEqual(got["payment_state"],"not_requested")
            self.assertFalse(got["auto_send_enabled"])

    def test_farm_price_is_unknown_not_invented(self):
        self.assertIsNone(self.offers.OFFERS["farm_break_even"]["packages"]["analysis"])
        model=next(x for x in self.port.catalogue()["items"] if x["code"]=="farm_break_even")
        self.assertIsNone(model["revenue_collected"])
        self.assertEqual(model["commercial_release"],"blocked_unverified")

    def test_existing_international_prices_are_exploratory_not_paid(self):
        v=self.offers.OFFERS["website_checkout_repair"]["packages"]
        self.assertEqual(v["diagnosis"]["indicative_min"],29)
        self.assertEqual(v["bounded_repair"]["indicative_max"],149)
        self.assertIsNone(self.port.catalogue()["collected_revenue"])

    def test_all_extra_income_models_remain_unverified(self):
        extra=[i for i in self.port.catalogue()["items"]
               if i["code"] not in self.offers.OFFERS]
        self.assertEqual(len(extra),9)
        self.assertTrue(all(i["source_status"]=="candidate_unverified" for i in extra))
        self.assertTrue(all(i["commercial_release"]=="blocked_unverified" for i in extra))

    def test_inquiry_handler_cannot_record_delivered_or_paid(self):
        entry={"offer":"website_checkout_repair","package":"diagnosis",
               "scope_items":2,"evidence_items":2,"consent_to_contact":True,
               "inputs_available":True,"synthetic_example":True}
        got=self.offers.qualify(entry)
        self.assertEqual(got["order_state"],"inquiry_only")
        self.assertEqual(got["delivery_state"],"not_delivered")
        self.assertFalse(got["personal_data_exported"])

    def test_unverified_cohort_cannot_be_promoted_to_revenue(self):
        source={"schema":"mojtaba.bot.ai.synthetic-funnel.v1",
                "synthetic_example":False,
                "counts":dict.fromkeys(self.port.FUNNEL_KEYS,0)}
        with self.assertRaises(ValueError):self.port.funnel(source)

    def test_source_plans_share_the_same_two_site_hosts(self):
        hosts={x["site"] for x in self.port.catalogue()["items"]}
        self.assertEqual(hosts,{"zomorodmelal.ir","mojplaywin.com"})
        self.assertEqual(self.port.catalogue()["candidate_model_count"],11)

if __name__=='__main__':unittest.main()

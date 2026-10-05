from django.test import TestCase
from core.factory_tool_pack import product_research, opportunity_score, product_spec, product_build_record, product_qa, product_localize, launch_candidate
from core.models import Product

class FactoryToolPackTests(TestCase):
    def test_chain_reaches_launch_candidate_with_evidence(self):
        r=product_research({"title":"Evidence Product","sources":[{"url":"https://example.com/a","finding":"demand"},{"url":"https://example.com/b","finding":"competition"}]})
        pid=r["product_id"]
        opportunity_score({"product_id":pid,"score":82,"rationale":"evidence"})
        product_spec({"product_id":pid,"spec":{"problem":"costly manual work","acceptance_criteria":["saves time"]}})
        product_build_record({"product_id":pid,"artifact":{"ref":"git:abc123"}})
        product_qa({"product_id":pid,"tests":{"passed":True},"security":{"passed":True}})
        product_localize({"product_id":pid,"locales":["en","fa"]})

    def test_invalid_research_is_rejected(self):
        with self.assertRaises(ValueError):
            product_research({"title":"No evidence","sources":[]})

    def test_launch_requires_allowed_market(self):
        r=product_research({"title":"P","sources":[{"url":"https://example.com/a","finding":"a"},{"url":"https://example.com/b","finding":"b"}]})
        pid=r["product_id"]
        opportunity_score({"product_id":pid,"score":70})
        product_spec({"product_id":pid,"spec":{"problem":"p","acceptance_criteria":["a"]}})
        product_build_record({"product_id":pid,"artifact":{"ref":"git:x"}})
        product_qa({"product_id":pid,"tests":{"passed":True},"security":{"passed":True}})
        product_localize({"product_id":pid,"locales":["en"]})
        with self.assertRaises(ValueError):
            launch_candidate({"product_id":pid,"markets":[{"country":"XX","eligibility":"pending_review"}]})
        out=launch_candidate({"product_id":pid,"markets":[{"country":"US","eligibility":"allowed"}]})
        self.assertEqual(out["factory_state"],"launch_candidate")
        self.assertFalse(Product.objects.get(pk=pid).active)

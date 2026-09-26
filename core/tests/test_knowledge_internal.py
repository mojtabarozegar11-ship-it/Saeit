from django.test import TestCase
from django.urls import reverse

from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeBook, KnowledgeDomain


class KnowledgeInternalPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plan = KnowledgeAgentPlan.objects.create(code="test-plan", title="Test Plan", mission="test", goal="test")
        cls.domain = KnowledgeDomain.objects.create(code="test-domain", title="حوزه آزمایشی", scientific_scope="دامنه پژوهش آزمایشی", priority=1)
        cls.book = KnowledgeBook.objects.create(plan=cls.plan, code="test-book", title="کتاب آزمایشی", domain="حوزه آزمایشی", domain_ref=cls.domain, objective="هدف آزمایشی", target_sections=10)

    def test_domain_page_is_public(self):
        response = self.client.get(reverse("knowledge_domain_detail", args=[self.domain.code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حوزه آزمایشی")

    def test_book_page_is_public_and_does_not_claim_publication(self):
        response = self.client.get(reverse("knowledge_book_detail", args=[self.book.code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کتاب آزمایشی")
        self.assertContains(response, "محتوای این عنوان هنوز تولید یا تأیید نشده است")

    def test_knowledge_index_exposes_agent_governance_and_publication_gate(self):
        response = self.client.get("/knowledge/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "موتور زنده تولید و کنترل دانش")
        self.assertContains(response, "OWNER APPROVAL")
        self.assertContains(response, "هنوز مقاله‌ای با وضعیت انتشار عمومی ثبت نشده است.")

    def test_sitemap_contains_knowledge_book_and_domain(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/knowledge/book/{self.book.code}/")
        self.assertContains(response, f"/knowledge/domain/{self.domain.code}/")

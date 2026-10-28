"""Public knowledge surfaces must never expose draft, planned or review books."""
from django.test import TestCase

from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeBook, KnowledgeDomain


class KnowledgeBookPublicationGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        plan = KnowledgeAgentPlan.objects.create(
            code="publication-gate-20261028",
            title="Publication gate plan",
            mission="Protect unpublished book records",
            goal="Publish only approved public releases",
        )
        domain = KnowledgeDomain.objects.create(
            code="publication-gate-domain",
            title="Controlled research domain",
            scientific_scope="Publication safety",
            active=True,
        )
        cls.published = KnowledgeBook.objects.create(
            plan=plan,
            domain_ref=domain,
            code="needle2026-published",
            title="Needle2026 Published Book",
            domain="Publication safety",
            objective="A released knowledge record",
            status="published",
            content="Released content only",
        )
        cls.published_related = KnowledgeBook.objects.create(
            plan=plan,
            domain_ref=domain,
            code="needle2026-published-related",
            title="Needle2026 Published Related",
            domain="Publication safety",
            objective="Another released record",
            status="published",
        )
        cls.draft = KnowledgeBook.objects.create(
            plan=plan,
            domain_ref=domain,
            code="needle2026-draft",
            title="Needle2026 Draft Book",
            domain="Publication safety",
            objective="Internal draft only",
            status="drafting",
            content="Confidential draft content marker",
        )
        cls.planned = KnowledgeBook.objects.create(
            plan=plan,
            domain_ref=domain,
            code="needle2026-planned",
            title="Needle2026 Planned Book",
            domain="Publication safety",
            objective="Internal planned only",
            status="planned",
        )

    def test_only_published_book_detail_is_public(self):
        response = self.client.get("/knowledge/book/needle2026-published/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Needle2026 Published Book")
        self.assertContains(response, "Needle2026 Published Related")
        self.assertNotContains(response, "Needle2026 Draft Book")
        for code in ("needle2026-draft", "needle2026-planned"):
            with self.subTest(code=code):
                self.assertEqual(self.client.get(f"/knowledge/book/{code}/").status_code, 404)

    def test_domain_index_excludes_unpublished_books(self):
        response = self.client.get("/knowledge/domain/publication-gate-domain/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Needle2026 Published Book")
        self.assertContains(response, "Needle2026 Published Related")
        self.assertNotContains(response, "Needle2026 Draft Book")
        self.assertNotContains(response, "Needle2026 Planned Book")

    def test_public_search_excludes_unpublished_books(self):
        response = self.client.get("/search/", {"q": "Needle2026"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/knowledge/book/needle2026-published/")
        self.assertContains(response, "/knowledge/book/needle2026-published-related/")
        self.assertNotContains(response, "/knowledge/book/needle2026-draft/")
        self.assertNotContains(response, "/knowledge/book/needle2026-planned/")

    def test_sitemap_only_advertises_published_books(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("/knowledge/book/needle2026-published/", body)
        self.assertIn("/knowledge/book/needle2026-published-related/", body)
        self.assertNotIn("/knowledge/book/needle2026-draft/", body)
        self.assertNotIn("/knowledge/book/needle2026-planned/", body)


if __name__ == "__main__":
    import unittest
    unittest.main()

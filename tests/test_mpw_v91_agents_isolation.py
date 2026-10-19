"""Regression: MojPlayWin-only V91 agents, not Zomorod/factory/subsites."""
import json
import unittest
from pathlib import Path

from mpw_v91_port.runtime import (
    MojPlayWinAgentInputError, review_draft, valid_main_host,
)

class V91AgentPortTests(unittest.TestCase):
    def test_original_v91_agent_generation_code_really_copied(self):
        base=Path(__file__).resolve().parents[1]/"mpw_v91_port"/"legacy"
        for rel in ("site_master/bridge.py",
                    "site_master/vendor/master_gen64/controller.py",
                    "site_master/vendor/master_gen56/controller.py",
                    "portal/agent_engine.py","portal/generator.py"):
            self.assertTrue((base/rel).is_file(),rel)
        origin=json.loads((base.parent/"ORIGIN.json").read_text())
        self.assertGreaterEqual(origin["file_count"],70)
        self.assertEqual(origin["scope"],"MojPlayWin main site ONLY; excluded all other sites")

    def test_main_host_only(self):
        for name in ("mojplaywin.com","www.mojplaywin.com","mojplaywin.com:443"):
            self.assertTrue(valid_main_host(name))
        for name in ("zomorodmelal.ir","example.com","mojplaywin.com.evil.example",
                     "mojplaywin.com/mojtaba.roozegar","studio.mojplaywin.com","127.0.0.1"):
            self.assertFalse(valid_main_host(name))

    def test_reject_unsafe_or_excessive_inputs(self):
        valid=self._sample()
        for delta in (
            {"kind":"publish_site"},
            {"body":"short"},
            {"sources":["http://example.org"]},
            {"sources":["file:///etc/passwd"]},
            {"sources":["https://user:secret@example.org"]},
            {"sources":[]},
            {"title":"x"*500},
        ):
            with self.subTest(delta=list(delta)):
                with self.assertRaises(MojPlayWinAgentInputError):
                    review_draft({**valid,**delta})

    @staticmethod
    def _sample():
        return {
            "kind":"research_digest",
            "title":"مطالعه آزمایشی برنامه‌ریزی پژوهش و مدیریت",
            "summary":"این متن صرفاً یک نمونه آزمایشی برای بررسی روش دسته‌بندی اطلاعات پژوهشی است و برای انتشار تهیه نشده است.",
            "body":("این پاراگراف یک نمونه آزمایشی برای خلاصه‌سازی اطلاعات علمی از منبع تأییدشده است. "
                    "داده‌ها ساختگی هستند و ادعای صحت درباره واقعیت‌های جهان ندارند. ")*8,
            "sources":["https://example.org/"],
        }

    def test_actual_original_gen64_master_and_editorial_engine_review(self):
        # These assertions require real imported V91 source files. No mocks.
        sample=self._sample()
        result=review_draft(sample)
        self.assertEqual(result["tenant"],"mojplaywin-main")
        self.assertEqual(result["legacy_origin"],"V91-master-gen64")
        self.assertEqual(result["engine_version"],"9.1")
        self.assertEqual(result["provenance"],"published_site_article")
        self.assertTrue(result["body"])
        self.assertTrue(result["review_required"])
        self.assertFalse(result["published"])
        self.assertFalse(result["sale_ready"])

    def test_original_product_blueprint_agent_is_review_only(self):
        draft=review_draft({**self._sample(),"kind":"product_blueprint"})
        self.assertEqual(draft["tenant"],"mojplaywin-main")
        self.assertTrue(draft["review_required"])
        self.assertFalse(draft["sale_ready"])

class MainSitePreviewSecurityTests(unittest.TestCase):
    def test_flag_defaults_off(self):
        from django.conf import settings
        self.assertFalse(getattr(settings,"MOJPLAYWIN_V91_AGENT_REVIEW_ENABLED",False))

    def test_staff_only_and_other_host_denied(self):
        from django.test import RequestFactory,override_settings
        from django.http import Http404
        from types import SimpleNamespace
        from core.mojplaywin_v91_agent_views import mojplaywin_v91_agent_preview
        factory=RequestFactory()
        payload=json.dumps(V91AgentPortTests._sample(),ensure_ascii=False)
        with override_settings(ALLOWED_HOSTS=["mojplaywin.com","zomorodmelal.ir"],
                               MOJPLAYWIN_V91_AGENT_REVIEW_ENABLED=True):
            req=factory.post("/agents/v91/review/",data=payload,content_type="application/json",
                             HTTP_HOST="zomorodmelal.ir")
            req.user=SimpleNamespace(is_authenticated=True,is_staff=True)
            # Bypass CSRF only for this direct-view test so host isolation is exercised.
            # Production requests still require the real CSRF cookie and token.
            req._dont_enforce_csrf_checks=True
            with self.assertRaises(Http404):
                mojplaywin_v91_agent_preview(req)
            req=factory.post("/agents/v91/review/",data=payload,content_type="application/json",
                             HTTP_HOST="mojplaywin.com")
            req._dont_enforce_csrf_checks=True
            req.user=SimpleNamespace(is_authenticated=False,is_staff=False)
            self.assertEqual(mojplaywin_v91_agent_preview(req).status_code,403)
            req.user=SimpleNamespace(is_authenticated=True,is_staff=True)
            answer=mojplaywin_v91_agent_preview(req)
            self.assertEqual(answer.status_code,200)
            self.assertIn('"published": false',answer.content.decode().lower())

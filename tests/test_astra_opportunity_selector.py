"""Offline synthetic fixtures: source links are NOT verified market evidence."""
import importlib.util
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_opportunity_selector.py"
spec = importlib.util.spec_from_file_location("astra_opportunity_selector_qa", str(SCRIPT))
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)

NOW = "2026-10-15T00:00:00Z"
MEASURES = {
    "problem_intensity": 75,
    "demand": 70,
    "differentiation": 60,
    "feasibility": 80,
    "margin": 70,
    "distribution": 70,
    "strategic_fit": 80,
}
GATES = {
    "lawful": True, "rights_reviewed": True,
    "build_capability_available": True,
    "distribution_path_available": True,
}


def candidate(key, **updates):
    d = {
        "opportunity_key": key,
        "problem": "A hypothetical buyer needs a verifiable farm cost comparison",
        "assessments": dict(MEASURES),
        "gates": dict(GATES),
    }
    d.update(updates)
    return d


def evidence(key, host, claim, *, date="2026-10-14T00:00:00Z", digest=None):
    return {
        "opportunity_key": key,
        "url": "https://" + host + "/synthetic-test-only",
        "content_sha256": digest or hashlib.sha256((key + host + claim).encode()).hexdigest(),
        "claim_type": claim,
        "observed_at": date,
    }


def pair(key):
    """A minimal two-claim dossier, deliberately insufficient for review."""
    return [evidence(key, "example.com", "problem"),
            evidence(key, "example.org", "willingness_to_pay")]


def review_evidence(key):
    """Synthetic complete dossier used only to exercise review eligibility."""
    return [evidence(key, "example.com", "problem"),
            evidence(key, "example.org", "willingness_to_pay"),
            evidence(key, "example.net", "comparison"),
            evidence(key, "example.com", "feasibility")]


def run_rank(candidates, sources):
    return selector.rank_opportunities(candidates, sources, NOW)


class AstraOpportunitySelectorTests(unittest.TestCase):
    def test_two_domains_with_problem_and_payment_only_stay_in_research(self):
        row = run_rank([candidate("thin")], pair("thin"))["candidates"][0]
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertIn("FEWER_THAN_THREE_DISTINCT_SOURCE_DOMAINS", row["blockers"])
        self.assertIn("COMPETITOR_COMPARISON_SIGNAL_MISSING", row["blockers"])
        self.assertIn("FEASIBILITY_SIGNAL_MISSING", row["blockers"])

    def test_one_point_topic_never_reaches_review_even_with_complete_links(self):
        one_point = {k: 1 for k in MEASURES}
        row = run_rank(
            [candidate("weak", assessments=one_point)],
            review_evidence("weak"),
        )["candidates"][0]
        self.assertEqual(row["priority_score"], 1)
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertIn("PROVISIONAL_PRIORITY_BELOW_RESEARCH_FLOOR", row["blockers"])
        self.assertFalse(row["build_authorized"])

    def test_evidence_and_capability_are_review_not_build_permission(self):
        report = run_rank([candidate("farm-1")], review_evidence("farm-1"))
        entry = report["candidates"][0]
        self.assertEqual(entry["status"], "REVIEW_REQUIRED")
        self.assertEqual(entry["distinct_source_domains_preliminary"], 3)
        self.assertEqual(entry["claim_source_domains_preliminary"]["comparison"], 1)
        self.assertFalse(entry["evidence_verified_independently"])
        self.assertFalse(entry["build_authorized"])
        self.assertFalse(entry["publish_authorized"])
        self.assertFalse(entry["payment_authorized"])
        self.assertEqual(report["new_products_built"], 0)
        self.assertEqual(report["paid_calls"], 0)

    def test_empty_evidence_never_auto_qualifies_high_score(self):
        high = {k: 100 for k in MEASURES}
        row = run_rank([candidate("high", assessments=high)], [])["candidates"][0]
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertEqual(row["priority_score"], 100)
        self.assertIn("FEWER_THAN_THREE_DISTINCT_SOURCE_DOMAINS", row["blockers"])

    def test_one_domain_is_not_independent_sources(self):
        sources = [evidence("farm", "example.com", "problem"),
                   evidence("farm", "example.com", "willingness_to_pay")]
        row = run_rank([candidate("farm")], sources)["candidates"][0]
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertEqual(row["distinct_source_domains_preliminary"], 1)

    def test_two_links_without_willingness_to_pay_do_not_qualify(self):
        sources = [evidence("farm", "example.com", "problem"),
                   evidence("farm", "example.org", "comparison")]
        row = run_rank([candidate("farm")], sources)["candidates"][0]
        self.assertEqual(row["status"], "RESEARCH_REQUIRED")
        self.assertIn("PROBLEM_OR_WILLINGNESS_SIGNAL_MISSING", row["blockers"])

    def test_disallowed_domains_and_invalid_sources_are_ignored(self):
        bad = [("127.0.0.1", "https://127.0.0.1/a"),
               ("local", "https://localhost/a"),
               ("http", "http://example.net/a"),
               ("userinfo", "https://user:pass@example.net/a"),
               ("internal", "https://host.internal/a"),
               ("invalid", "https://host.invalid/a")]
        for _, url in bad:
            with self.subTest(url=url):
                one = pair("farm")[:1]
                s = evidence("farm", "example.net", "willingness_to_pay")
                s["url"] = url
                row = run_rank([candidate("farm")], one + [s])["candidates"][0]
                self.assertEqual(row["status"], "RESEARCH_REQUIRED")

    def test_expired_future_and_invalid_sha_not_accepted(self):
        for changes in (
            {"observed_at": "2025-01-01T00:00:00Z"},
            {"observed_at": "2026-10-16T00:00:00Z"},
            {"content_sha256": "not-a-sha"},
        ):
            with self.subTest(changes=changes):
                s = pair("farm")
                s[1].update(changes)
                row = run_rank([candidate("farm")], s)["candidates"][0]
                self.assertEqual(row["status"], "RESEARCH_REQUIRED")

    def test_lawful_and_rights_are_nonnegotiable(self):
        for name in ("lawful", "rights_reviewed"):
            with self.subTest(gate=name):
                g = dict(GATES)
                g[name] = False
                row = run_rank([candidate("farm", gates=g)], pair("farm"))["candidates"][0]
                self.assertEqual(row["status"], "REJECTED")

    def test_unavailable_builder_or_distribution_stops_review_promotion(self):
        for name in ("build_capability_available", "distribution_path_available"):
            with self.subTest(gate=name):
                g = dict(GATES)
                g[name] = False
                row = run_rank([candidate("farm", gates=g)], pair("farm"))["candidates"][0]
                self.assertEqual(row["status"], "RESEARCH_REQUIRED")
                self.assertIn("BUILD_OR_DISTRIBUTION_CAPABILITY_MISSING", row["blockers"])

    def test_evidence_not_product_id_drives_review_order(self):
        a = candidate("999")
        b = candidate("001", assessments={k: 100 for k in MEASURES})
        rows = run_rank([b, a], review_evidence("999"))["candidates"]
        self.assertEqual([x["opportunity_key"] for x in rows], ["999", "001"])
        self.assertEqual(rows[1]["status"], "RESEARCH_REQUIRED")

    def test_evidence_change_reorders_candidates(self):
        a, b = candidate("a"), candidate("b")
        first = run_rank([a, b], review_evidence("a"))["candidates"]
        later = run_rank([b, a], review_evidence("b"))["candidates"]
        self.assertEqual(first[0]["opportunity_key"], "a")
        self.assertEqual(later[0]["opportunity_key"], "b")

    def test_scoring_changes_order_with_same_synthetic_source_sufficiency(self):
        higher = {k: 95 for k in MEASURES}
        lower = {k: 35 for k in MEASURES}
        rows = run_rank([candidate("low", assessments=lower),
                         candidate("high", assessments=higher)],
                        review_evidence("low") + review_evidence("high"))["candidates"]
        self.assertEqual([x["opportunity_key"] for x in rows], ["high", "low"])

    def test_same_input_is_deterministic_and_has_no_order_dependency(self):
        a, b = candidate("a"), candidate("b")
        sources = review_evidence("a") + review_evidence("b")
        one = run_rank([b, a], list(reversed(sources)))
        two = run_rank([a, b], sources)
        self.assertEqual(one, two)
        self.assertNotIn("order", json.dumps(one).lower())
        self.assertTrue(all(not x["build_authorized"] for x in one["candidates"]))

    def test_duplicate_keys_and_invalid_scores_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_rank([candidate("a"), candidate("a")], [])
        with self.assertRaisesRegex(ValueError, "assessment"):
            run_rank([candidate("a", assessments={**MEASURES, "demand": True})], [])
        with self.assertRaisesRegex(ValueError, "assessment"):
            run_rank([candidate("a", assessments={**MEASURES, "margin": 101})], [])

    def test_overly_large_batches_fail(self):
        with self.assertRaisesRegex(ValueError, "batch"):
            run_rank([candidate("a")] * 2001, [])
        with self.assertRaisesRegex(ValueError, "snapshot"):
            run_rank([], [{}] * 10001)

    def test_cli_writes_private_local_review_not_publication(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "test-only.json"
            out = Path(root) / "review-only.json"
            src.write_text(json.dumps({
                "candidates": [candidate("farm")], "snapshots": pair("farm")
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(src),
                 "--output", str(out), "--now-utc", NOW],
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ASTRA_SELECTOR_BUILD_AUTHORIZED=false", result.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(payload["candidates"][0]["build_authorized"])
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()

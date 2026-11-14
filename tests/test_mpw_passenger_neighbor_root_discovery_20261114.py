"""Fingerprint-only immediate cPanel app root discovery; synthetic filesystem."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mpw_onepass_cpanel_source_provenance_readonly_20261113 as probe


class NeighborRootDiscoveryTests(unittest.TestCase):
    def setUp(self):
        h=tempfile.TemporaryDirectory()
        self.addCleanup(h.cleanup)
        self.home=Path(h.name)

    def root(self, name="app", markers=("wsgi",)):
        base=self.home/name
        base.mkdir()
        rels={
            "wsgi":"passenger_wsgi.py",
            "manage":"manage.py",
            "store":"core/mojplaywin_views.py",
            "checkout":"mpw_commerce/product_checkout_page.py",
        }
        for marker in markers:
            file=base/rels[marker]
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(b"# synthetic code only\n")
        return base

    def inspect(self):
        return probe.discover_neighbor_app_roots(self.home)

    def test_01_empty_home_returns_bounded_scan(self):
        self.assertEqual(self.inspect()["status"],"bounded_immediate_home_scan")

    def test_02_no_fake_root_in_empty_home(self):
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_03_wsgifile_yields_candidate_fingerprint(self):
        root=self.root()
        a=self.inspect()
        self.assertEqual(a["candidate_count"],1)
        self.assertEqual(a["candidates"][0]["root_sha256_prefix"],
                         hashlib.sha256(str(root).encode()).hexdigest()[:16])

    def test_04_no_absolute_home_paths_in_output(self):
        self.root()
        self.assertNotIn(str(self.home),str(self.inspect()))

    def test_05_no_directory_names_in_output(self):
        self.root(name="sensitive-business-name")
        self.assertNotIn("sensitive-business-name",str(self.inspect()))

    def test_06_candidate_does_not_prove_effective_worker(self):
        self.root()
        self.assertFalse(self.inspect()["effective_passenger_worker_attested"])

    def test_07_candidate_cannot_authorize_release(self):
        self.root()
        self.assertFalse(self.inspect()["release_permitted"])

    def test_08_per_candidate_no_checkout_claim(self):
        self.root(markers=("wsgi","manage","store","checkout"))
        self.assertFalse(self.inspect()["candidates"][0]["effective_checkout_verified"])

    def test_09_candidate_is_not_registered_root_proof(self):
        self.root()
        self.assertFalse(self.inspect()["candidates"][0]["registered_root_verified"])

    def test_10_wsgi_only_is_distinct_category(self):
        self.root()
        self.assertEqual(self.inspect()["candidates"][0]["marker_class"],"wsgi_marker_only")

    def test_11_source_only_three_markers_are_candidate(self):
        self.root(markers=("manage","store","checkout"))
        self.assertEqual(self.inspect()["candidate_count"],1)

    def test_12_source_only_classifies_correctly(self):
        self.root(markers=("manage","store","checkout"))
        self.assertEqual(self.inspect()["candidates"][0]["marker_class"],
                         "mpw_checkout_source_markers")

    def test_13_wsgi_and_checkout_markers_are_distinct(self):
        self.root(markers=("wsgi","store","checkout"))
        self.assertEqual(self.inspect()["candidates"][0]["marker_class"],
                         "wsgi_and_mpw_checkout_markers")

    def test_14_manage_without_checkout_does_not_claim_mpw(self):
        self.root(markers=("manage",))
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_15_checkout_without_store_does_not_claim_app(self):
        self.root(markers=("manage","checkout"))
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_16_store_without_checkout_does_not_claim_app(self):
        self.root(markers=("manage","store"))
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_17_unrelated_regular_file_does_not_claim_app(self):
        root=self.root(markers=())
        (root/"readme.txt").write_text("private")
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_18_symlinked_direct_child_not_followed(self):
        root=self.root()
        (self.home/"linked-app").symlink_to(root,target_is_directory=True)
        self.assertEqual(self.inspect()["candidate_count"],1)

    def test_19_symlinked_home_is_denied(self):
        other=self.home.parent/"not-saved-home-link"
        # Link inside same temporary workspace so no external access.
        alias=self.home/"alias"
        alias.symlink_to(self.home,target_is_directory=True)
        self.assertEqual(probe.discover_neighbor_app_roots(alias)["status"],
                         "home_unavailable_or_unsafe")

    def test_20_symlinked_wsgi_file_not_counted(self):
        root=self.root(markers=())
        (root/"passenger_wsgi.py").symlink_to(root/"nonexistent")
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_21_symlinked_source_parent_not_counted(self):
        root=self.root(markers=("manage",))
        internal=root/"elsewhere"
        internal.mkdir()
        (internal/"mojplaywin_views.py").write_bytes(b"source")
        (internal/"product_checkout_page.py").write_bytes(b"source")
        (root/"core").symlink_to(internal,target_is_directory=True)
        (root/"mpw_commerce").symlink_to(internal,target_is_directory=True)
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_22_zero_byte_wsgi_not_counted(self):
        root=self.root(markers=("wsgi",))
        (root/"passenger_wsgi.py").write_bytes(b"")
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_23_oversize_wsgi_not_counted(self):
        root=self.root(markers=("wsgi",))
        (root/"passenger_wsgi.py").write_bytes(b"A"*240001)
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_24_more_than_96_entries_fail_closed(self):
        self.root()
        for n in range(97):
            (self.home/("misc"+str(n))).mkdir()
        a=self.inspect()
        self.assertEqual(a["status"],"entry_budget_exceeded")
        self.assertEqual(a["candidate_count"],0)

    def test_25_at_most_96_entries_accepted(self):
        self.root()
        for n in range(95):
            (self.home/("misc"+str(n))).mkdir()
        self.assertEqual(self.inspect()["status"],"bounded_immediate_home_scan")

    def test_26_more_than_16_candidate_roots_rejected(self):
        for n in range(17):
            self.root(name="c"+str(n))
        a=self.inspect()
        self.assertEqual(a["status"],"candidate_budget_exceeded")
        self.assertEqual(a["candidates"],[])

    def test_27_exactly_16_candidates_allowed(self):
        for n in range(16):
            self.root(name="c"+str(n))
        self.assertEqual(self.inspect()["candidate_count"],16)

    def test_28_candidates_sorted_by_fingerprint_not_path(self):
        self.root(name="z")
        self.root(name="a")
        got=[x["root_sha256_prefix"] for x in self.inspect()["candidates"]]
        self.assertEqual(got,sorted(got))

    def test_29_file_marker_no_contents_in_report(self):
        root=self.root()
        (root/"passenger_wsgi.py").write_bytes(b"SECRET_CUSTOMER_PASSWORD"*20)
        self.assertNotIn("SECRET_CUSTOMER",str(self.inspect()))

    def test_30_missing_home_refuses_evidence(self):
        missing=self.home/"does-not-exist"
        self.assertEqual(probe.discover_neighbor_app_roots(missing)["status"],
                         "home_unavailable_or_unsafe")

    def test_31_candidate_is_only_one_level_deep(self):
        deep=self.home/"nested"
        deep.mkdir()
        nested=deep/"child"
        nested.mkdir()
        (nested/"passenger_wsgi.py").write_bytes(b"source")
        self.assertEqual(self.inspect()["candidate_count"],0)

    def test_32_boolean_counts_are_sane(self):
        self.root()
        a=self.inspect()
        self.assertEqual(a["inspected_entries_capped"],1)
        self.assertFalse(a["release_permitted"])

    def test_33_caller_uses_synthetic_parent_not_global_home(self):
        a=self.home/"Saeit-staging"
        a.mkdir()
        b=self.home/"mojplaywin.com"
        b.mkdir()
        (a/"passenger_wsgi.py").write_bytes(b"hello")
        report=probe.inspect(a,b)
        self.assertEqual(report["neighbor_root_fingerprints"]["candidate_count"],1)

    def test_34_legacy_runtime_still_not_claimed_with_candidate(self):
        a=self.home/"Saeit-staging";a.mkdir()
        b=self.home/"mojplaywin.com";b.mkdir()
        (a/"passenger_wsgi.py").write_bytes(b"fake")
        report=probe.inspect(a,b)
        self.assertFalse(report["effective_django_template_origin_verified"])

    def test_35_source_unchanged_cannot_verify_invoice_or_revenue(self):
        a=self.home/"Saeit-staging";a.mkdir()
        b=self.home/"mojplaywin.com";b.mkdir()
        (a/"passenger_wsgi.py").write_bytes(b"fake")
        report=probe.inspect(a,b)
        self.assertIsNone(report["confirmed_revenue"])
        self.assertFalse(report["production_invoice_post_verified"])

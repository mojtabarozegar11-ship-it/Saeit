"""Real owner-route vacancy proof contract; fixture-only, no network."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_plan1_sidecar_vacancy_readonly as m


class VacancyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/"home"
        self.home.mkdir(mode=0o700)
        self.doc=self.home/"mojplaywin.com"
        self.doc.mkdir(mode=0o755)
        self.parent=self.doc/"moj-prop"
        self.parent.mkdir(mode=0o755)
        (self.parent/"index.html").write_text("existing owner homepage")
        (self.parent/"contact").mkdir()
        (self.parent/"contact/index.html").write_text("existing owner contact")

    def test_01_absent_new_route_is_a_safe_candidate_only(self):
        self.assertEqual(m.classify(self.parent),"safe_absent")

    def test_02_empty_owned_route_is_safe_candidate(self):
        (self.parent/"plan1").mkdir()
        self.assertEqual(m.classify(self.parent),"safe_empty_directory")

    def test_03_existing_owner_page_is_never_called_vacant(self):
        route=self.parent/"plan1"
        route.mkdir()
        (route/"index.html").write_text("owner live page")
        self.assertEqual(m.classify(self.parent),"occupied_do_not_replace")

    def test_04_unknown_extra_file_is_occupied(self):
        route=self.parent/"plan1"
        route.mkdir()
        (route/"keep.txt").write_text("owner record")
        self.assertEqual(m.classify(self.parent),"occupied_do_not_replace")

    def test_05_symlinked_route_is_occupied_not_vacant(self):
        (self.parent/"plan1").symlink_to(self.doc, target_is_directory=True)
        self.assertEqual(m.classify(self.parent),"occupied_do_not_replace")

    def test_06_unsafe_world_writable_parent_blocks(self):
        self.parent.chmod(0o777)
        self.assertEqual(m.classify(self.parent),"unsafe_or_unavailable")

    def test_07_symlinked_parent_is_not_trusted(self):
        target=self.home/"elsewhere"
        self.parent.rename(target)
        self.parent.symlink_to(target, target_is_directory=True)
        self.assertEqual(m.classify(self.parent),"unsafe_or_unavailable")

    def test_08_foreign_owner_classification_fails_closed(self):
        self.assertEqual(m.classify(self.parent,os.geteuid()+1000),"unsafe_or_unavailable")

    def test_09_unsafe_missing_parent_never_means_vacant(self):
        self.parent.rename(self.doc/"other-route")
        self.assertEqual(m.classify(self.parent),"unsafe_or_unavailable")

    def test_10_http200_is_not_evidence_of_nonoccupancy(self):
        p=self.parent/"plan1"
        p.mkdir();(p/"index.html").write_text("not ours")
        r=m.inspect(self.parent,lambda:200)
        self.assertEqual(r["public_http_status"],200)
        self.assertFalse(r["vacant_for_new_additive_source"])
        self.assertEqual(r["route_status"],"occupied_do_not_replace")

    def test_11_http404_does_not_allow_unknown_existing_files(self):
        p=self.parent/"plan1";p.mkdir();(p/"data").write_text("keep")
        r=m.inspect(self.parent,lambda:404)
        self.assertFalse(r["vacant_for_new_additive_source"])

    def test_12_http404_and_safe_absence_are_two_independent_facts(self):
        r=m.inspect(self.parent,lambda:404)
        self.assertTrue(r["vacant_for_new_additive_source"])
        self.assertEqual(r["public_http_status"],404)
        self.assertFalse(r["production_release_authorized"])

    def test_13_network_exception_becomes_zero_not_approval(self):
        def broken(): raise TimeoutError("no network")
        r=m.inspect(self.parent,broken)
        self.assertEqual(r["public_http_status"],0)
        self.assertFalse(r["production_release_authorized"])

    def test_14_status_enum_is_closed(self):
        self.assertEqual(m.STATES,{"safe_absent","safe_empty_directory",
                                   "occupied_do_not_replace","unsafe_or_unavailable"})

    def test_15_no_user_content_in_metadata_only_report(self):
        (self.parent/"index.html").write_text("private-opaque-irrelevant")
        result=m.inspect(self.parent,lambda:200)
        self.assertNotIn("private-opaque",str(result))
        self.assertTrue(result["read_only"])
        self.assertTrue(result["no_file_data_or_customer_data_read"])
        self.assertTrue(result["existing_home_contact_preserved"])

    def test_16_no_post_write_or_secret_read_code(self):
        s=Path(m.__file__).read_text("utf-8")
        self.assertIn('method="GET"',s)
        self.assertNotIn('method="POST"',s)
        self.assertNotIn("write_text(",s)
        self.assertNotIn("write_bytes(",s)
        self.assertNotIn("os.environ[",s)
        self.assertNotIn("shutil.rmtree",s)

    def test_17_safe_check_does_not_create_new_directory(self):
        m.inspect(self.parent,lambda:404)
        self.assertFalse((self.parent/"plan1").exists())

    def test_18_no_directory_names_returned_even_when_occupied(self):
        p=self.parent/"plan1";p.mkdir()
        (p/"sensitive-file-xyz").write_text("not for logs")
        r=m.inspect(self.parent,lambda:404)
        self.assertNotIn("sensitive-file-xyz",str(r))

    def test_19_route_is_literal_owner_subpath(self):
        self.assertEqual(m.SIDE,"plan1")
        self.assertEqual(m.URL,"https://mojplaywin.com/moj-prop/plan1/")
        self.assertEqual(m.PARENT,Path("/home/zomorod2/mojplaywin.com/moj-prop"))

    def test_21_empty_dir_is_not_installable_until_owner_review(self):
        (self.parent/"plan1").mkdir()
        r=m.inspect(self.parent,lambda:404)
        self.assertEqual(r["route_status"],"safe_empty_directory")
        self.assertFalse(r["vacant_for_new_additive_source"])
        self.assertFalse(r["production_release_authorized"])

    def test_20_report_does_not_claim_lawful_paid_enrollment(self):
        r=m.inspect(self.parent,lambda:404)
        self.assertFalse(r["production_release_authorized"])
        self.assertFalse(r["payment_or_email_sent"])


if __name__=="__main__":
    unittest.main()

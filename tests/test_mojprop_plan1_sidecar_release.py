"""Strict synthetic safety suite for additive Plan1 sidecar; NO live writes."""
from __future__ import annotations
from html.parser import HTMLParser
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_plan1_sidecar_release as m

REPO = Path(__file__).resolve().parents[1]
REVIEWED = REPO / "templates/moj-prop-plan1-sidecar/index.html"
ENABLED = {key: "true" for key in m.REQUIRED_ENV}


class HTMLSafety(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = 0
        self.scripts = []
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms += 1
        if tag == "script":
            self.scripts.append(a.get("type", ""))
        if tag == "a":
            self.hrefs.append(a.get("href", ""))


class SidecarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.docroot = self.home / "mojplaywin.com"
        self.docroot.mkdir(mode=0o755)
        self.parent = self.docroot / "moj-prop"
        self.parent.mkdir(mode=0o755)
        self.root_home = self.parent / "index.html"
        self.root_home.write_text("OWNER ORIGINAL HOME — DO NOT TOUCH", encoding="utf-8")
        self.contact = self.parent / "contact"
        self.contact.mkdir()
        (self.contact / "index.html").write_text("OWNER CONTACT — DO NOT TOUCH")
        self.run = "777"
        self.stage = self.home / (".mojprop-plan1-sidecar-stage-" + self.run)
        self.stage.mkdir(mode=0o700)
        (self.stage / "templates").mkdir()
        (self.stage / "templates/moj-prop-plan1-sidecar").mkdir()
        self.staged = self.stage / "templates/moj-prop-plan1-sidecar/index.html"
        self.staged.write_bytes(REVIEWED.read_bytes())
        self.staged.chmod(0o600)

    def preflight(self):
        return m.inspect(self.run, home=self.home, parent=self.parent)

    def install(self, auth=None):
        return m.install(self.run, home=self.home, parent=self.parent,
                         authorization=ENABLED if auth is None else auth)

    def test_01_fixed_exact_reviewed_github_blob(self):
        self.assertEqual(m.git_blob_id(REVIEWED.read_bytes()), m.SOURCE_GIT_BLOB)

    def test_02_precise_source_byte_identity(self):
        self.assertEqual(m.staged_source(self.run, self.home), REVIEWED.read_bytes())

    def test_03_plan1_is_an_additive_subpath_only(self):
        self.assertEqual(m.SIDE, "plan1")
        self.assertEqual(str(m.SOURCE_REL), "templates/moj-prop-plan1-sidecar/index.html")

    def test_04_preflight_does_not_change_owner_file_or_create_target(self):
        before = self.root_home.read_bytes()
        result = self.preflight()
        self.assertTrue(result["read_only"])
        self.assertEqual(result["destination_status"], "absent")
        self.assertTrue(result["can_add_without_overwriting"])
        self.assertFalse((self.parent / "plan1").exists())
        self.assertEqual(self.root_home.read_bytes(), before)

    def test_05_source_is_bilingual(self):
        page = REVIEWED.read_text("utf-8")
        self.assertIn('lang="en"', page)
        self.assertIn('id="fa" lang="fa" dir="rtl"', page)
        self.assertIn("MOJ-PROP-01", page)

    def test_06_price_is_non_transactional_native_trx(self):
        text = REVIEWED.read_text("utf-8")
        self.assertIn("30,000,000 SUN", text)
        self.assertIn("30 TRX", text)
        self.assertIn("Not open for paid enrollment", text)
        self.assertIn("فروش و پرداخت فعال نیست", text)

    def test_07_no_html_application_or_post_forms(self):
        parsed = HTMLSafety()
        parsed.feed(REVIEWED.read_text("utf-8"))
        self.assertEqual(parsed.forms, 0)
        self.assertEqual(parsed.scripts, ["application/ld+json"])

    def test_08_no_broken_consent_or_checkout_links(self):
        s = REVIEWED.read_text("utf-8")
        self.assertNotIn("/moj-prop-interest/form/", s)
        self.assertNotIn("/checkout/", s)
        self.assertNotIn("window.location", s)
        self.assertNotIn("fetch(", s)

    def test_09_first_party_nonbinding_mailto(self):
        parser = HTMLSafety()
        parser.feed(REVIEWED.read_text("utf-8"))
        self.assertTrue(any(s.startswith("mailto:support@mojplaywin.com?")
                            for s in parser.hrefs))
        self.assertTrue(all(s.startswith("#") or s.startswith("mailto:support@mojplaywin.com?")
                            for s in parser.hrefs))

    def test_10_separate_from_starter30_educational_product(self):
        text=REVIEWED.read_text("utf-8")
        self.assertIn("MOJPROP-STARTER30", text)
        self.assertIn("are separate", text)

    def test_11_canonical_is_new_route_not_owner_root(self):
        self.assertIn('href="https://mojplaywin.com/moj-prop/plan1/"',
                      REVIEWED.read_text("utf-8"))

    def test_12_revision_is_a_draft_without_broker_promises(self):
        page=REVIEWED.read_text("utf-8")
        self.assertIn("payment disabled", page)
        self.assertIn("No actual funding", page)
        self.assertIn("Not financial advice", page)

    def test_13_refuse_bad_run_ids(self):
        for value in ("../1", "", "1/2", "x", "-1", "1"*30, " 1", "7;rm"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.run_id(value)

    def test_14_refuse_tampered_staged_html(self):
        self.staged.write_bytes(self.staged.read_bytes()+b"ALTERED")
        with self.assertRaisesRegex(RuntimeError,"reviewed immutable"):
            self.preflight()

    def test_15_refuse_staged_symlink(self):
        self.staged.unlink()
        self.staged.symlink_to(REVIEWED)
        with self.assertRaisesRegex(RuntimeError,"Untrusted staged"):
            self.preflight()

    def test_16_refuse_stage_world_writable(self):
        self.stage.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError,"Unsafe private staged root"):
            self.preflight()

    def test_17_refuse_staged_hardlink(self):
        extra=self.stage/"templates/moj-prop-plan1-sidecar/copy.html"
        os.link(self.staged,extra)
        with self.assertRaisesRegex(RuntimeError,"Untrusted staged"):
            self.preflight()

    def test_18_refuse_bad_parent_permission(self):
        self.parent.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError,"Untrusted current website parent"):
            self.preflight()

    def test_19_refuse_parent_symlink(self):
        destination=self.home/"other-route"
        self.parent.rename(destination)
        self.parent.symlink_to(destination, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,"Untrusted current website parent"):
            self.preflight()

    def test_20_install_requires_all_independent_release_grants(self):
        for key in m.REQUIRED_ENV:
            auth=dict(ENABLED)
            auth[key]="false"
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError,"approvals absent"):
                self.install(auth)
        self.assertFalse((self.parent/"plan1").exists())

    def test_21_install_creates_only_new_sidecar_and_preserves_both_originals(self):
        oldhome=self.root_home.read_bytes()
        oldcontact=(self.contact/"index.html").read_bytes()
        r=self.install()
        self.assertEqual(r["status"],"created_new_path_only")
        self.assertEqual((self.parent/"plan1/index.html").read_bytes(),REVIEWED.read_bytes())
        self.assertEqual(self.root_home.read_bytes(),oldhome)
        self.assertEqual((self.contact/"index.html").read_bytes(),oldcontact)
        self.assertEqual(sorted(x.name for x in (self.parent/"plan1").iterdir()),["index.html"])

    def test_22_identical_second_install_is_idempotent(self):
        self.install()
        first=(self.parent/"plan1/index.html").stat().st_mtime_ns
        r=self.install()
        self.assertEqual(r["status"],"already_identical")
        self.assertEqual((self.parent/"plan1/index.html").stat().st_mtime_ns,first)

    def test_23_unknown_live_plan1_blocks_overwrite(self):
        target=self.parent/"plan1"
        target.mkdir()
        previous=target/"index.html"
        previous.write_text("OWNER FOREIGN PAGE")
        with self.assertRaisesRegex(RuntimeError,"cannot be overwritten"):
            self.install()
        self.assertEqual(previous.read_text(),"OWNER FOREIGN PAGE")

    def test_24_symlinked_live_plan1_blocks_install(self):
        (self.parent/"plan1").symlink_to(self.contact, target_is_directory=True)
        self.assertFalse(self.preflight()["can_add_without_overwriting"])
        with self.assertRaisesRegex(RuntimeError,"cannot be overwritten"):
            self.install()
        self.assertEqual((self.contact/"index.html").read_text(),"OWNER CONTACT — DO NOT TOUCH")

    def test_25_unknown_extra_files_block_install(self):
        route=self.parent/"plan1"
        route.mkdir()
        (route/"index.html").write_bytes(REVIEWED.read_bytes())
        (route/"owner-note.txt").write_bytes(b"keep")
        self.assertEqual(self.preflight()["destination_status"],"blocked_existing_directory")
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual((route/"owner-note.txt").read_bytes(),b"keep")

    def test_26_existing_hardlinked_sidecar_blocks_install(self):
        route=self.parent/"plan1"
        route.mkdir()
        (route/"index.html").write_bytes(REVIEWED.read_bytes())
        os.link(route/"index.html",self.home/"hidden-copy")
        self.assertEqual(self.preflight()["destination_status"],"blocked_existing_source")

    def test_27_existing_sidecar_world_writable_blocks_install(self):
        route=self.parent/"plan1"
        route.mkdir()
        item=route/"index.html"
        item.write_bytes(REVIEWED.read_bytes())
        item.chmod(0o666)
        self.assertEqual(self.preflight()["destination_status"],"blocked_existing_source")

    def test_28_unknown_route_blocks_on_preflight(self):
        (self.parent/"plan1").write_text("not a directory")
        self.assertEqual(self.preflight()["destination_status"],"blocked_existing_directory")

    def test_29_no_shell_deletion_replace_or_db_code(self):
        s=Path(m.__file__).read_text("utf-8")
        self.assertNotIn("os.replace(",s)
        self.assertNotIn("shutil.rmtree",s)
        self.assertNotIn("DROP TABLE",s)
        self.assertNotIn("mysqldump",s)
        self.assertIn("os.O_EXCL",s)
        self.assertIn("os.link(tmp, \"index.html\"",s)

    def test_30_no_live_email_trx_or_customer_post_claim(self):
        report=self.preflight()
        self.assertFalse(report["payment_or_customer_data_enabled"])
        self.assertFalse(report["full_restore_independently_observed_by_this_code"])
        self.assertTrue(report["existing_owner_home_contact_preserved"])


    def test_31_og_title_does_not_claim_verified_draft(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("Moj Prop Plan 1 — draft rules, prelaunch only", s)
        self.assertNotIn("Moj Prop Plan 1 — verified rules", s)

    def test_32_social_post_clause_not_approved(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("Social-post conditions are under contract review", s)
        self.assertIn("no social post is requested while paid enrollment is closed", s)

    def test_33_no_false_xauusd_three_percent_launch(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("prospective v1.3 source-only order preflight now enforces", s)
        self.assertIn("broker-verified exact XAUUSD symbol", s)
        self.assertIn("up to 3% per-order / 8% aggregate open stop-risk", s)
        self.assertIn("NOT live, customer-authorized or enabled for real orders", s)
        self.assertNotIn("policy is NOT implemented", s)

    def test_34_existing_engine_limits_are_stated(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("0.8% order risk / 1.6% aggregate open risk", s)

    def test_35_proposed_risk_always_discloses_drawdown(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("4% daily and 8% total drawdown limits", s)
        self.assertIn("افت روزانه ۴٪ و کل ۸٪", s)

    def test_36_profit_split_conditional_not_paid(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("70% trader / 30% organizer", s)
        self.assertIn("No actual funding, brokerage execution or profit distribution is enabled", s)

    def test_37_persian_risk_status_does_not_claim_deployment(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("در کد توسعه پیاده‌سازی و آزمون شده", s)
        self.assertIn("هنوز روی سایت زنده منتشر نشده", s)
        self.assertIn("معاملات واقعی فعال نیست", s)

    def test_38_public_page_still_has_no_registration_or_payment_form(self):
        parsed = HTMLSafety()
        parsed.feed(REVIEWED.read_text("utf-8"))
        self.assertEqual(parsed.forms, 0)
        self.assertEqual(parsed.scripts, ["application/ld+json"])
        self.assertIn("payment disabled", REVIEWED.read_text("utf-8"))

    def test_39_new_gold_contract_is_distinct_and_not_publicly_active(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("2026-11-17/v1.3", s)
        self.assertIn("Historical v1.2", s)
        self.assertIn("0.8% order risk / 1.6% aggregate open risk", s)
        self.assertIn("it is NOT installed on the public site", s)

    def test_40_customer_pays_nothing_until_real_separate_approval(self):
        s = REVIEWED.read_text("utf-8")
        self.assertIn("Not open for paid enrollment", s)
        self.assertIn("No wallet address, payment instruction", s)
        self.assertIn("No payment, challenge application or consent form is active", s)
        self.assertIn("سقف سخت‌گیرانه افت روزانه ۴٪ و کل ۸٪", s)


if __name__ == "__main__":
    unittest.main()

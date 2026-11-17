"""C158 deterministic fake GETs, no production or network calls."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_c158_owner_origin_parity_readonly as c


class SyntheticOriginParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "moj-prop"
        self.root.mkdir(mode=0o700)
        (self.root / "contact").mkdir(mode=0o700)

    def put(self, name, raw, mode=0o600):
        path = self.root / c.FILES[name][0]
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def fake(self, replies):
        return lambda url: replies[url]

    def test_01_fixed_https_same_origin_urls_only(self):
        self.assertEqual(set(c.FILES), {"home", "contact"})
        self.assertTrue(all(u.startswith("https://mojplaywin.com/moj-prop/")
                            for _, u in c.FILES.values()))

    def test_02_url_allowlist_denies_exfiltration(self):
        with self.assertRaises(ValueError):
            c.public_get("https://bad.example/collect")

    def test_03_unsafe_root_denied(self):
        r, raw = c.disk_bytes(self.root, "home", os.geteuid()+7)
        self.assertEqual((r, raw), ("unsafe_root", b""))

    def test_04_missing_disk_file_denied(self):
        self.assertEqual(c.disk_bytes(self.root, "home")[0], "missing")

    def test_05_unsafe_world_writable_file_not_read(self):
        self.put("home", b"test", 0o666)
        self.assertEqual(c.disk_bytes(self.root, "home")[0], "unsafe_file")

    def test_06_symlink_cannot_escape(self):
        external = Path(self.tmp.name) / "outside"
        external.write_bytes(b"private")
        (self.root / "index.html").symlink_to(external)
        self.assertEqual(c.disk_bytes(self.root, "home")[0], "unsafe_file")

    def test_07_hardlink_cannot_escape(self):
        self.put("home", b"test")
        os.link(self.root / "index.html", self.root / "copy")
        self.assertEqual(c.disk_bytes(self.root, "home")[0], "unsafe_file")

    def test_08_symlink_directory_denied(self):
        (self.root / "contact").rmdir()
        (self.root / "contact").symlink_to(self.root, target_is_directory=True)
        self.assertEqual(c.disk_bytes(self.root, "contact")[0], "unsafe_parent")

    def test_09_maximum_source_size_enforced(self):
        self.put("home", b"x" * (c.MAX_BYTES+1))
        self.assertEqual(c.disk_bytes(self.root, "home")[0], "unsafe_file")

    def test_10_exact_bytes_match_only_not_an_authorization(self):
        home = b'<html>MOJ-PROP-01 PRELAUNCH</html>'
        contact = b'<html><a href="mailto:support@mojplaywin.com">Email</a></html>'
        self.put("home", home); self.put("contact", contact)
        replies = {
            c.FILES["home"][1]: (200, home),
            c.FILES["contact"][1]: (200, contact),
        }
        result = c.inspect(self.root, self.fake(replies))
        self.assertTrue(result["all_public_pages_exact_disk"])
        self.assertFalse(result["commercial_readiness_verified"])
        self.assertTrue(result["no_post_no_payment_no_email_no_release"])
        self.assertTrue(result["pages"]["home"]["disk_flags"]["funded_plan1_sku_marked"])

    def test_11_http200_different_body_fails_parity(self):
        self.put("home", b"<html>one</html>")
        self.put("contact", b"<html>two</html>")
        data = self.fake({
            c.FILES["home"][1]: (200, b"<html>new</html>"),
            c.FILES["contact"][1]: (200, b"<html>two</html>"),
        })
        r = c.inspect(self.root, data)
        self.assertFalse(r["all_public_pages_exact_disk"])
        self.assertEqual(r["pages"]["home"]["http_vs_disk"], "different_bytes")
        self.assertEqual(r["pages"]["contact"]["http_vs_disk"], "exact_match")

    def test_12_404_or_network_failure_not_a_match(self):
        self.put("home", b"<html>one</html>")
        self.put("contact", b"<html>two</html>")
        r = c.inspect(self.root, self.fake({
            c.FILES["home"][1]: (404, b""),
            c.FILES["contact"][1]: (0, b""),
        }))
        self.assertFalse(r["all_public_pages_exact_disk"])
        self.assertTrue(all(p["http_vs_disk"]=="unavailable" for p in r["pages"].values()))

    def test_13_absent_does_not_guess_parity(self):
        r=c.inspect(self.root,self.fake({
            c.FILES["home"][1]:(200,b"<html>one</html>"),
            c.FILES["contact"][1]:(200,b"<html>two</html>"),
        }))
        self.assertFalse(r["all_public_pages_exact_disk"])
        self.assertEqual(r["pages"]["home"]["http_vs_disk"],"unavailable")

    def test_14_semantic_markers_stay_bounded_to_flags(self):
        data=(b'<a href="/moj-prop-interest/form/?lang=fa">bad</a>'
              b'<a href="mailto:support@mojplaywin.com?subject=MOJ-PROP-01">Support</a>'
              b'<form action="/moj-prop-intake/"></form>'
              b'<a href="/checkout/">Buy</a>'
              b'MOJPROP-STARTER30 prelaunch')
        flags=c.semantic_flags(data)
        self.assertTrue(flags["known_unavailable_consent_link"])
        self.assertTrue(flags["official_support_mailto_present"])
        self.assertTrue(flags["generic_service_form_action"])
        self.assertTrue(flags["checkout_link_present"])
        self.assertTrue(flags["educational_starter30_sku_marked"])
        self.assertEqual(set(flags), {
            "funded_plan1_sku_marked","educational_starter30_sku_marked",
            "prelaunch_word_present","known_unavailable_consent_link",
            "official_support_mailto_present","generic_service_form_action",
            "checkout_link_present",
        })

    def test_15_no_token_customer_secrets_or_http_body_in_report(self):
        data=b'<html> private-string-should-never-appear</html>'
        self.put("home",data)
        self.put("contact",data)
        out=c.inspect(self.root,self.fake({u:(200,data) for _,u in c.FILES.values()}))
        text=str(out)
        self.assertNotIn("private-string-should-never-appear",text)
        self.assertNotIn("sha256",text)
        self.assertNotIn("token",text)
        self.assertNotIn("/home/",text)

    def test_17_pure_structural_summary_never_contains_content_or_attr(self):
        html = (b'<!doctype html><html><head><title>PRIVATE-TITLE-123</title>'
                b'<meta http-equiv="refresh" content="1;url=/private">'
                b'</head><body><script src="/private.js">location.replace("/abc")'
                b'</script><a href="/private-path">Visible</a><iframe src="/secret">'
                b'</iframe></body></html>')
        shape = c.structural_flags(html)
        self.assertTrue(shape["doctype_html"])
        self.assertTrue(shape["script_element"])
        self.assertTrue(shape["external_script"])
        self.assertTrue(shape["iframe_element"])
        self.assertTrue(shape["meta_refresh"])
        self.assertTrue(shape["javascript_location_navigation"])
        self.assertTrue(shape["title_element"])
        self.assertTrue(shape["anchor_element"])
        self.assertNotIn("PRIVATE-TITLE-123", str(shape))
        self.assertNotIn("/private", str(shape))

    def test_18_loader_shell_is_structurally_observable_but_not_ready(self):
        raw = b'<html><body><script src="/app.js"></script></body></html>'
        flags = c.structural_flags(raw)
        self.assertTrue(flags["external_script"])
        self.assertEqual(flags["visible_text_band"], "none")
        self.assertFalse(flags["anchor_element"])
        self.assertFalse(flags["form_element"])
        self.assertFalse(flags["doctype_html"])

    def test_19_missing_disk_source_has_no_shape_and_never_approves(self):
        report = c.inspect(self.root, self.fake({
            c.FILES["home"][1]: (200, b"fake"),
            c.FILES["contact"][1]: (200, b"fake"),
        }))
        self.assertIsNone(report["pages"]["home"]["disk_shape"])
        self.assertFalse(report["all_public_pages_exact_disk"])

    def test_20_bounded_bands_never_return_lengths(self):
        self.assertEqual(c._band(0), "none")
        self.assertEqual(c._band(1), "tiny")
        self.assertEqual(c._band(2048), "small")
        self.assertEqual(c._band(8192), "medium")
        self.assertEqual(c._band(32768), "large")
        self.assertEqual(c._band(98304), "very_large")

    def test_16_source_declares_no_POST_or_body_logging(self):
        src=Path(c.__file__).read_text("utf-8")
        self.assertIn('method="GET"',src)
        self.assertIn('MAX_BYTES = 196608',src)
        self.assertNotIn('method="POST"',src)
        self.assertNotIn("print(raw)",src)
        self.assertNotIn("os.environ[",src)


if __name__=="__main__":
    unittest.main()

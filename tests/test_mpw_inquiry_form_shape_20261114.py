"""Strict MojPlayWin first-party lead decoder tests (source-only / no POST).

The PHP function under test is extracted and executed in CLI isolation. The
endpoint/session/storage/mail code is never included or executed by these tests.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mpw_revenue_20261020/earn/inquiry.php"

def source_text():
    return SOURCE.read_text(encoding="utf-8")

def isolated_form_guard():
    source = source_text()
    match = re.search(
        r"(^function inquiry_input_violations\(array \$post, \$contentType, \$rawBody\): array \{[\s\S]+?^\})",
        source, re.MULTILINE,
    )
    if match is None:
        raise AssertionError("Owned PHP form-decoder helper was not found")
    return match.group(1)

class InquiryFormShapeTests(unittest.TestCase):
    maxDiff = 2000

    def valid_post(self):
        return {
            "csrf": "a"*48,
            "service": "website-doctor",
            "name": "Ada Applicant",
            "email": "ada@example.org",
            "company": "Example Co",
            "website": "https://example.org",
            "details": "I need a bounded checkout audit and a report on three clear bugs.",
            "timeline": "During the next month",
            "fax_number": "",
            "consent": "yes",
        }

    def evaluate(self, *, post_extra=None, post_remove=None,
                 content_type="application/x-www-form-urlencoded",
                 raw_body=None, raw_body_suffix="", bad_utf8=False):
        php = shutil.which("php")
        if not php:
            self.skipTest("PHP CLI unavailable")
        post = self.valid_post()
        post.update(post_extra or {})
        for key in (post_remove or []):
            post.pop(key, None)
        # Deliberately derive raw bytes from the original valid form for
        # mismatch and malformed-PHP-normalization adversarial cases.
        raw = urlencode(self.valid_post()) if raw_body is None else raw_body
        raw += raw_body_suffix
        php_src = (
            "if(!function_exists('mb_check_encoding')) {"
            "function mb_check_encoding($s,$enc='UTF-8'){return preg_match('//u',$s)===1;}}"
            "if(!function_exists('mb_strlen')) {"
            "function mb_strlen($s,$enc='UTF-8'){return preg_match_all('/./us',$s);}}"
            + isolated_form_guard() + "\n"
            + "$c=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);"
            + "if(!empty($c['bad_utf8'])) $c['post']['name']=chr(255);"
            + "$e=inquiry_input_violations($c['post'],$c['content_type'],$c['raw_body']);"
            + "echo json_encode(['accepted'=>count($e)===0,'errors'=>count($e)]);"
        )
        run = subprocess.run(
            [php, "-r", php_src],
            input=json.dumps({
                "post": post, "content_type": content_type,
                "raw_body": raw, "bad_utf8": bad_utf8,
            }), capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr[:700])
        return json.loads(run.stdout)["accepted"]

    def test_valid_browser_submission_accepted(self):
        self.assertTrue(self.evaluate())

    def test_explicit_utf8_content_type_accepted(self):
        self.assertTrue(self.evaluate(content_type="application/x-www-form-urlencoded; charset=UTF-8"))

    def test_non_ascii_buyer_text_accepted(self):
        name="علی رضایی"
        details="درخواست ممیزی وب‌سایت و گزارش فنی و بررسی روش پرداخت آنلاین با توضیحات کافی."
        post=self.valid_post()
        post.update(name=name,details=details)
        self.assertTrue(self.evaluate(post_extra={"name":name,"details":details},
                                      raw_body=urlencode(post)))

    def test_exact_field_limit_accepted(self):
        post=self.valid_post()
        post["name"]="A"*120
        self.assertTrue(self.evaluate(post_extra={"name":post["name"]},raw_body=urlencode(post)))

    def test_lead_writes_only_after_guard(self):
        s=source_text()
        self.assertLess(s.index("inquiry_input_violations($_POST"),s.index("$reference=store_inquiry($record)"))
        self.assertIn("$rawBody=@file_get_contents('php://input',false,null,0,12001);",s)
        self.assertIn("!empty($_FILES)",s)
        self.assertIn("http_response_code(400)",s)

    def test_no_false_revenue_or_parallel_bot(self):
        s=source_text()
        self.assertIn("No payment, binding order or contract is created.",s)
        self.assertNotIn("paid_orders=1",s)
        self.assertNotIn("received_revenue=1",s)
        self.assertNotIn("new autonomous worker",s)

    def test_private_record_preserved_when_notification_fails(self):
        s=source_text()
        self.assertIn("MPW_INQUIRY_OWNER_NOTIFICATION_FAILED",s)
        self.assertLess(s.index("$reference=store_inquiry($record)"),s.index("@mail(MPW_OFFICIAL_INQUIRY_EMAIL"))
        self.assertIn("openssl_encrypt($plain,'aes-256-gcm'",s)

    def test_session_token_type_guard(self):
        s=source_text()
        self.assertIn("is_string($priorToken)",s)
        self.assertIn("bin2hex(random_bytes(24))",s)

    def test_php_lint(self):
        php=shutil.which("php")
        if not php:
            self.skipTest("PHP CLI unavailable")
        run=subprocess.run([php,"-l",str(SOURCE)],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_gate_01_content_type_absent(self):
        self.assertFalse(self.evaluate(**{'content_type': None}))

    def test_gate_02_multipart_rejected(self):
        self.assertFalse(self.evaluate(**{'content_type': 'multipart/form-data; boundary=abc'}))

    def test_gate_03_actual_chunked_size_limit(self):
        self.assertFalse(self.evaluate(**{'raw_body': 'x'*12001}))

    def test_gate_04_empty_raw_body(self):
        self.assertFalse(self.evaluate(**{'raw_body': ''}))

    def test_gate_05_raw_semicolon_separator(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': ';evil=1'}))

    def test_gate_06_invalid_percent_escape(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': '&email=%Q3'}))

    def test_gate_07_empty_raw_field_key(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': '&=x'}))

    def test_gate_08_overlong_raw_field_key(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': '&'+'a'*100+'=x'}))

    def test_gate_09_unknown_raw_field(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': '&surprise=1'}))

    def test_gate_10_duplicate_raw_email(self):
        self.assertFalse(self.evaluate(**{'raw_body_suffix': '&email=second%40example.org'}))

    def test_gate_11_unexpected_decoded_post_field(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'surprise': '1'}}))

    def test_gate_12_nested_array_email(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'email': ['x@example.org']}}))

    def test_gate_13_malformed_utf8_field(self):
        self.assertFalse(self.evaluate(**{'bad_utf8': True}))

    def test_gate_14_overlong_name_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'name':'A'*121}}))

    def test_gate_15_overlong_email_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'email':'x'*255}}))

    def test_gate_16_overlong_company_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'company':'x'*121}}))

    def test_gate_17_overlong_website_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'website':'x'*301}}))

    def test_gate_18_overlong_details_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'details':'x'*2001}}))

    def test_gate_19_overlong_timeline_without_truncation(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'timeline':'x'*121}}))

    def test_gate_20_newline_in_name(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'name':'Aa\nBb'}}))

    def test_gate_21_control_byte_in_details(self):
        self.assertFalse(self.evaluate(**{'post_extra': {'details':'text\x00description'}}))

    def test_gate_22_missing_service_post_even_when_get_exists(self):
        self.assertFalse(self.evaluate(**{'post_remove': ['service']}))

    def test_gate_23_missing_csrf_post(self):
        self.assertFalse(self.evaluate(**{'post_remove': ['csrf']}))

    def test_gate_24_missing_consent_post(self):
        self.assertFalse(self.evaluate(**{'post_remove': ['consent']}))

    def test_gate_25_mismatched_raw_body_fields(self):
        self.assertFalse(self.evaluate(**{'raw_body': 'service=website-doctor&name=Test'}))

if __name__ == "__main__":
    unittest.main()

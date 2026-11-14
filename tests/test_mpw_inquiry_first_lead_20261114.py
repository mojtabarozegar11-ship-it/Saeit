"""Read-only proof of exact first-party MojPlayWin inquiry source behavior.

No mail, HTTP POST, external credentials, real customer records or server writes.
Tests focus on accepted sales leads and preserving security and privacy gates.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mpw_revenue_20261020/earn/inquiry.php"
DEPLOYER = ROOT / "scripts/mpw_revenue_integrated_upgrade_20261026.py"
PHP_SESSION_WORKFLOW = ROOT / ".github/workflows/mpw-inquiry-cookie-session-repair-20261026.yml"
PUBLIC_OFFER_ROOT = ROOT / "mpw_revenue_20261020/earn"
OFFICIAL_EMAIL = "mojplaywin@gmail.com"
SERVICES = (
    "website-doctor", "landing-page-studio", "ai-automation",
    "business-spreadsheets", "website-templates", "social-media-kits",
    "resume-builder", "logo-studio", "browser-games", "marketing-ai",
    "business-calculators", "website-care",
)


def contents():
    return SOURCE.read_text(encoding="utf-8")


def php_limit(cases):
    """Execute ONLY the isolated pure helper, never the live inquiry endpoint."""
    interpreter = shutil.which("php")
    if not interpreter:
        pytest.skip("PHP CLI unavailable")
    source = contents()
    function = re.search(
        r"(^function oversized_inquiry_body\(\$raw\): bool \{[\s\S]+?^\})",
        source, re.MULTILINE,
    )
    assert function is not None, "Bounded PHP body guard missing"
    rows = ",".join(
        "[" + json.dumps(value) + "," + ("true" if expected else "false") + "]"
        for value, expected in cases
    )
    executable = (
        function.group(1) + "\n"
        "$cases=[" + rows + "];"
        "foreach($cases as $case) {"
        "if(oversized_inquiry_body($case[0]) !== $case[1]) {"
        "fwrite(STDERR, 'SIZE_GUARD_ASSERTION_FAILED');exit(17);"
        "}"
        "}echo 'LIMIT_TEST_OK';"
    )
    p = subprocess.run(
        [interpreter, "-r", executable],
        capture_output=True, text=True, timeout=8, check=False,
    )
    assert p.returncode == 0, p.stderr[:300]
    assert p.stdout.strip() == "LIMIT_TEST_OK"


def test_php_syntax_clean_without_executing_form():
    interpreter = shutil.which("php")
    if not interpreter:
        pytest.skip("PHP CLI unavailable")
    p = subprocess.run(
        [interpreter, "-l", str(SOURCE)],
        capture_output=True, text=True, timeout=8, check=False,
    )
    assert p.returncode == 0, p.stdout + p.stderr


def test_exact_12000_byte_boundary_allowed_and_12001_rejected():
    php_limit([("11999", False), ("12000", False),
               ("12001", True), ("12002", True)])


def test_oversized_multiple_digits_never_bypass_limit():
    php_limit([("999999", True), ("999999999", True),
               ("9999999999", True), ("00000012001", True)])


def test_malformed_content_length_denied():
    php_limit([("12e3", True), ("-1", True),
               ("12000X", True), (" 12000", True),
               ("12000 ", True), ("+12000", True)])


def test_unset_or_empty_content_length_is_not_invented():
    php_limit([(None, False), ("", False), ("0", False)])


def test_php_body_limit_applied_before_persistence():
    text = contents()
    guard = "if (oversized_inquiry_body($_SERVER['CONTENT_LENGTH']??null))"
    assert guard in text
    assert text.index(guard) < text.index("$reference=store_inquiry($record)")
    assert "strlen((string)($_SERVER['CONTENT_LENGTH']??''))>6" not in text


def test_official_email_single_source_of_truth():
    text = contents()
    assert text.count("const MPW_OFFICIAL_INQUIRY_EMAIL = 'mojplaywin@gmail.com';") == 1
    assert "mailto:support@mojplaywin.com" not in text
    assert "Please email support@mojplaywin.com" not in text
    assert "$fallback='mailto:'.MPW_OFFICIAL_INQUIRY_EMAIL" in text


def test_notification_destination_follows_official_customer_mailbox():
    text = contents()
    assert "@mail(MPW_OFFICIAL_INQUIRY_EMAIL," in text
    assert "@mail('support@mojplaywin.com'," not in text
    assert text.index("$reference=store_inquiry($record)") < text.index(
        "@mail(MPW_OFFICIAL_INQUIRY_EMAIL,"
    )


def test_customer_visible_fallback_uses_official_mailbox():
    text = contents()
    assert "<?=h(MPW_OFFICIAL_INQUIRY_EMAIL)?>" in text
    assert 'href="<?=h($fallback)?>"' in text
    assert "mojplaywin@gmail.com" in text


def test_extension_failure_fallback_uses_official_mailbox():
    text = contents()
    assert "Please email '.h(MPW_OFFICIAL_INQUIRY_EMAIL).'.</p>" in text


def test_csrf_accepts_only_string_and_uses_constant_time_compare():
    text = contents()
    assert "$submittedCsrf=$_POST['csrf']??null;" in text
    assert "!is_string($submittedCsrf) || !hash_equals($token,$submittedCsrf)" in text
    assert "(string)($_POST['csrf']??'')" not in text


def test_service_slug_rejects_array_injection():
    text = contents()
    assert "$slug=is_string($slugValue) ? $slugValue : '';" in text
    assert "if (!array_key_exists($slug,$allowed))" in text


def test_mandatory_valid_reply_email_and_client_consent_kept():
    text = contents()
    assert "FILTER_VALIDATE_EMAIL" in text
    assert "($_POST['consent']??'')!=='yes'" in text
    assert '<input type="email" name="email" required' in text
    assert '<input type="checkbox" name="consent" value="yes" required' in text


def test_encrypted_private_lead_receipt_and_no_new_public_pii_log():
    text = contents()
    assert "openssl_encrypt($plain,'aes-256-gcm'" in text
    assert "safe_private_dir()" in text
    assert "store_inquiry($record)" in text
    assert "error_log('MPW_INQUIRY_STORAGE_FAILURE')" in text
    assert "error_log($record)" not in text
    assert "no-store, private" in text


def test_antispam_honeypot_and_throttle_not_removed():
    text = contents()
    assert "if (!empty($_POST['fax_number']))" in text
    assert "if (time()-(int)($_SESSION['last_mpw_inquiry']??0)<90)" in text
    assert 'name="fax_number"' in text


def test_security_headers_and_secure_session_cookie_kept():
    text = contents()
    for marker in ("Content-Security-Policy:", "X-Content-Type-Options:",
                   "X-Frame-Options:", "session_set_cookie_params(",
                   "'secure'=>true", "'httponly'=>true",
                   "'samesite'=>'Lax'"):
        assert marker in text


def test_exact_12_service_slugs_still_accepted():
    text = contents()
    match = re.search(r"\$allowed\s*=\s*\[(.*?)\];", text, re.DOTALL)
    assert match
    ids = re.findall(r"'([a-z0-9-]+)'\s*=>", match.group(1))
    assert len(ids) == 13
    assert set(ids) == {"general", *SERVICES}


def test_twelve_service_detail_pages_have_correct_first_party_inquiry_links():
    for slug in SERVICES:
        html = (PUBLIC_OFFER_ROOT / slug / "index.html").read_text("utf-8")
        assert f"/earn/inquiry.php?service={slug}" in html


def test_deployment_rewrites_source_earn_routes_without_guessing_host_mapping():
    source = DEPLOYER.read_text("utf-8")
    assert 'data.replace(b"/earn/",b"/mpw-editorial/revenue/")' in source
    assert "mpw-editorial/revenue/inquiry.php?service=" in source
    # This is deployment source, NOT evidence it ran on live cPanel.


def test_cookie_path_contract_unchanged():
    text = contents()
    assert "'path'=>'/mpw-editorial/revenue' . '/'" in text
    workflow = PHP_SESSION_WORKFLOW.read_text("utf-8")
    assert "'Session cookie path regression'" in workflow


def test_notification_is_nonblocking_if_email_provider_unavailable():
    text = contents()
    assert "@mail(MPW_OFFICIAL_INQUIRY_EMAIL" in text
    assert "$sent=true;" in text
    assert text.index("$sent=true;") < text.index("@mail(MPW_OFFICIAL_INQUIRY_EMAIL")
    # A private saved lead cannot be discarded because PHP mail is unavailable.


def test_lead_confirmation_distinct_from_paid_order():
    text = contents()
    assert "No payment, binding order or contract is created." in text
    assert "Inquiry received" in text
    assert "Private record reference" in text
    assert "paid_receipt" not in text
    assert "charge_credit_card" not in text
    assert "send_trx" not in text


def test_form_post_action_matches_mapped_deployment_not_a_third_party():
    text = contents()
    assert 'method="post" action="/mpw-editorial/revenue/inquiry.php"' in text
    assert "form-action 'self'" in text


def test_owner_notification_body_excludes_buyer_details():
    text = contents()
    start = text.index('$body="MojPlayWin commercial inquiry')
    end = text.index("@mail(MPW_OFFICIAL_INQUIRY_EMAIL", start)
    snippet = text[start:end]
    assert '$data[' not in snippet
    assert '$reference' in snippet


def test_email_change_never_invents_paid_conversions():
    text = contents()
    assert "MPW_OFFICIAL_INQUIRY_EMAIL" in text
    assert "paid_orders=1" not in text
    assert "received_revenue=1" not in text


def test_integrated_upgrade_generated_quote_link_uses_official_mailbox():
    text = DEPLOYER.read_text("utf-8")
    assert "mailto:mojplaywin@gmail.com?subject=" in text
    assert "mailto:support@mojplaywin.com" not in text


def test_legacy_restore_generated_quote_links_use_official_mailbox():
    text = (ROOT / "scripts/mpw_revenue_12_restore_20261026.py").read_text("utf-8")
    assert text.count("mailto:mojplaywin@gmail.com?subject=") == 2
    assert "mailto:support@mojplaywin.com" not in text


def test_official_reply_path_consistent_across_all_three_source_generators():
    sources = [
        SOURCE, DEPLOYER,
        ROOT / "scripts/mpw_revenue_12_restore_20261026.py",
    ]
    for path in sources:
        text = path.read_text("utf-8")
        assert OFFICIAL_EMAIL in text
        assert "mailto:support@mojplaywin.com" not in text


def test_owner_dispatcher_remains_independent_private_reference_workflow():
    source = (ROOT / "scripts/mpw_revenue_owner_inquiry_dispatch_20261026.php"
              ).read_text("utf-8")
    assert "revenue-inquiries" in source
    assert "source" in source
    assert "owner-dispatched" in source
    # Dispatch verification is source-only; it is NOT proof live cron sends.
    assert "mojtaba.rozegar11@gmail.com" in source


def test_php_limit_handles_leading_zero_without_overflow_bypass():
    php_limit([("00012000", False), ("00012001", True),
               ("000000000", False), ("0000000000", True)])


def test_malformed_declared_content_length_is_fail_closed_not_infinite_request():
    php_limit([(True, True), (12000, True), (0, True),
               ("12000\n", True), ("12000\x00", True)])


def test_official_inbox_notification_is_an_attempt_not_revenue_proof():
    text = contents()
    assert "@mail(MPW_OFFICIAL_INQUIRY_EMAIL" in text
    assert "Review the private cPanel revenue-inquiries record." in text
    assert "$sent=true;" in text
    assert "No payment, binding order or contract is created." in text

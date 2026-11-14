"""Offline regression suite for one-bot revenue intake SOURCE evidence.

All tests use the local repository or copied synthetic fixtures. No network,
customer PII, payment, email, live host operations or external services.
"""
from pathlib import Path
import json
import shutil

import pytest

from scripts import mojtaba_revenue_source_gate_20261114 as gate


ROOT = Path(__file__).resolve().parents[1]
NEEDED = (
    gate.HUB, gate.INQUIRY, gate.STORE, gate.FARM,
    gate.BOT_MANIFEST, gate.BOT_EVIDENCE, gate.REVENUE_CONTRACT,
) + tuple(gate.SOURCE_ROOT + "/" + name + "/index.html"
          for name in gate.SERVICES)


@pytest.fixture
def sources(tmp_path):
    for relative in NEEDED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return tmp_path


def mutate(root, relative, old, new):
    p = root / relative
    contents = p.read_text("utf-8")
    assert old in contents
    p.write_text(contents.replace(old, new, 1), encoding="utf-8")


def test_twelve_real_service_landing_pages_link_to_own_form():
    result = gate.audit(ROOT)
    assert result["source_gate_passed"], [
        x for x in result["checks"] if not x["passed"]
    ]
    assert result["service_source_routes"] == {"linked": 12, "total": 12}
    assert len(result["service_offers"]) == 12
    assert len(result["checks"]) >= 50
    assert all(row["source_link_verified"] for row in result["service_offers"])


def test_no_paid_or_liveness_claims_or_working_bot_inferred():
    result = gate.audit(ROOT)
    for field in (
        "live_cpanel_checkout_verified", "live_inquiries_verified",
        "settled_paid_orders", "settled_revenue",
        "private_deliveries_verified", "canonical_bot_live_verified",
        "one_bot_cutover_verified",
    ):
        assert result[field] is None
    assert result["live_commercial_ready"] is False
    assert result["live_deployment_authorized"] is False


def test_single_bot_identity_and_no_new_scheduler_or_payment():
    result = gate.audit(ROOT)
    assert result["canonical_bot_id"] == "mojtaba.bot.ai"
    assert result["new_agents_created"] == 0
    assert result["payments_initiated"] == 0
    assert result["emails_sent"] == 0
    assert result["writes_performed"] == 0
    assert result["mode"] == "REPOSITORY_READ_ONLY"


def test_all_12_service_slugs_are_unique_and_allowlisted():
    assert len(set(gate.SERVICES)) == 12
    php = (ROOT / gate.INQUIRY).read_text("utf-8")
    assert gate._php_offer_ids(php) == set(gate.SERVICES) | {"general"}


def test_source_audit_blocks_wrong_service_detail_inquiry_url(sources):
    slug = "website-doctor"
    page = gate.SOURCE_ROOT + "/" + slug + "/index.html"
    p = sources / page
    old = p.read_text("utf-8")
    assert old.count("/earn/inquiry.php?service=website-doctor") >= 1
    p.write_text(old.replace("/earn/inquiry.php?service=website-doctor",
                             "/earn/inquiry.php?service=ai-automation"),
                 encoding="utf-8")
    result = gate.audit(sources)
    assert not result["source_gate_passed"]
    assert "service_page:website-doctor" in [
        v["code"] for v in result["checks"] if not v["passed"]
    ]


def test_source_audit_blocks_missing_service_hub_link(sources):
    mutate(sources, gate.HUB, 'href="/earn/website-doctor/"',
           'href="/other/website-doctor/"')
    # Main hub contains exactly one offer detail link for this category.
    result = gate.audit(sources)
    assert "hub_link:website-doctor" in [
        v["code"] for v in result["checks"] if not v["passed"]
    ]


def test_source_audit_blocks_php_allowlist_drift(sources):
    mutate(sources, gate.INQUIRY, "'website-doctor'=>", "'unreviewed-agent'=>")
    result = gate.audit(sources)
    assert not result["source_gate_passed"]
    assert not next(x for x in result["checks"]
                    if x["code"] == "php_all_services_and_general")["passed"]


def test_source_audit_rejects_removed_php_email_validation(sources):
    mutate(sources, gate.INQUIRY, "FILTER_VALIDATE_EMAIL", "NO_VALIDATION")
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "php_valid_email")["passed"]


def test_source_audit_rejects_removed_php_csrf_validation(sources):
    mutate(sources, gate.INQUIRY, "hash_equals(", "unvalidated_equals(")
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "php_csrf_check")["passed"]


def test_source_audit_rejects_removed_php_encryption_anchor(sources):
    mutate(sources, gate.INQUIRY, "aes-256-gcm", "plaintext")
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "php_encrypted_storage")["passed"]


def test_source_audit_rejects_noncanonical_extra_bot_id(sources):
    mutate(sources, gate.BOT_MANIFEST,
           '"canonical_bot_id": "mojtaba.bot.ai"',
           '"canonical_bot_id": "alternative.bot.ai"')
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "single_bot_identity")["passed"]


def test_source_audit_rejects_faked_bot_runtime_success(sources):
    mutate(sources, gate.BOT_EVIDENCE,
           '"production_deployment_attested": false',
           '"production_deployment_attested": true')
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "historical_not_deployment")["passed"]


def test_source_audit_rejects_fake_consolidation_percent(sources):
    mutate(sources, gate.BOT_EVIDENCE,
           '"whole_company_consolidation_pct": null',
           '"whole_company_consolidation_pct": 100')
    result = gate.audit(sources)
    assert not next(x for x in result["checks"]
                    if x["code"] == "historical_runtime_unknown")["passed"]


def test_source_guard_refuses_symlinked_service(sources):
    slug = "website-doctor"
    p = sources / gate.SOURCE_ROOT / slug / "index.html"
    p.unlink()
    p.symlink_to(ROOT / gate.SOURCE_ROOT / slug / "index.html")
    with pytest.raises(ValueError, match="SYMLINK_SOURCE_DENIED"):
        gate.audit(sources)


def test_source_guard_refuses_missing_site_file(sources):
    (sources / gate.INQUIRY).unlink()
    with pytest.raises(FileNotFoundError, match="SOURCE_MISSING"):
        gate.audit(sources)


def test_source_guard_refuses_relative_traversal(sources):
    for unsafe in ("../private/credentials", "/etc/passwd", "./test"):
        with pytest.raises(ValueError, match="UNSAFE_SOURCE_PATH"):
            gate._read(sources, unsafe)


def test_source_read_only_report_never_reports_sku879_as_checkout_verified():
    result = gate.audit(ROOT)
    assert result["product_ids"] == [72, 225, 879]
    assert next(x for x in result["checks"]
                if x["code"] == "store_879_details_only")["passed"]
    assert result["settled_paid_orders"] is None


def test_html_comment_only_inquiry_link_fails_closed(sources):
    slug = "website-doctor"
    file = gate.SOURCE_ROOT + "/" + slug + "/index.html"
    p = sources / file
    old = p.read_text("utf-8")
    assert old.count('href="/earn/inquiry.php?service=website-doctor"') >= 1
    p.write_text(old.replace('href="/earn/inquiry.php?service=website-doctor"',
                             'href="/earn/inquiry.php?service=unrelated"'),
                 encoding="utf-8")
    assert not gate.audit(sources)["source_gate_passed"]


def test_php_allowlist_parser_rejects_duplicate_entries():
    php = "$allowed = ['general'=>'General','general'=>'Repeat'];"
    assert gate._php_offer_ids(php) == set()


def test_report_markdown_still_says_revenue_unknown():
    report = gate.audit(ROOT)
    text = gate.markdown(report)
    assert "mojtaba.bot.ai" in text
    assert "UNKNOWN" in text
    assert "NOT AUTHORIZED" in text
    assert "12/12" in text


def test_no_network_or_money_transfers_in_source_gate_script():
    code = (ROOT / "scripts/mojtaba_revenue_source_gate_20261114.py").read_text("utf-8")
    for forbidden in ("urllib.request", "requests.post", "subprocess.run",
                      "smtplib", "send_mail(", "PaymentIntent.objects",
                      "os.system(", "shutil.rmtree(", ".write_text("):
        assert forbidden not in code


def test_revenue_contract_two_services_three_products_and_one_bot():
    result = gate.audit(ROOT)
    assert result["source_gate_passed"]
    assert result["pilot_service_ids"] == [
        "website-doctor", "farm-profitability-break-even"
    ]
    assert result["canonical_bot_id"] == "mojtaba.bot.ai"
    contract = json.loads((ROOT / gate.REVENUE_CONTRACT).read_text("utf-8"))
    assert len(contract["offers"]) == 2
    assert len(contract["digital_products"]) == 3
    assert all(entry["quote_mode"] == "manual_review_only"
               for entry in contract["offers"])
    assert all(entry["received_revenue_verified"] is False
               for entry in contract["offers"])


def test_revenue_contract_blocks_noncanonical_agent(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"canonical_bot_id": "mojtaba.bot.ai"',
           '"canonical_bot_id": "shadow-revenue.bot"')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_contract_identity")["passed"]


def test_revenue_contract_blocks_spend_activation(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"auto_spend_authorized": false',
           '"auto_spend_authorized": true')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_automatic_write_denied")["passed"]


def test_revenue_contract_blocks_fabricated_receipts(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"confirmed_paid_order_count": null',
           '"confirmed_paid_order_count": 3')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_paid_unknown")["passed"]


def test_revenue_contract_blocks_fabricated_delivery(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"delivery_verified_live": false',
           '"delivery_verified_live": true')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_product_scope")["passed"]


def test_revenue_contract_blocks_unsupported_service_claim(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"quote_mode": "manual_review_only"',
           '"quote_mode": "fully_automatic_paid_checkout"')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_service_scope")["passed"]


def test_revenue_contract_blocks_missing_payment_evidence(sources):
    mutate(sources, gate.REVENUE_CONTRACT,
           '"compliant_paid_receipt",',
           '"unverified_invoice_stub",')
    checks = gate.audit(sources)["checks"]
    assert not next(x for x in checks if
                    x["code"] == "revenue_manual_client_handoff")["passed"]


def test_contract_revenue_not_auto_sent_and_no_new_bot():
    source = (ROOT / gate.REVENUE_CONTRACT).read_text("utf-8")
    contract = json.loads(source)
    assert contract["single_bot_policy"].startswith("one_orchestrator")
    assert contract["auto_email_authorized"] is False
    assert contract["auto_publication_authorized"] is False
    assert contract["automatic_live_trading_authorized"] is False
    assert contract["confirmed_revenue_amount"] is None

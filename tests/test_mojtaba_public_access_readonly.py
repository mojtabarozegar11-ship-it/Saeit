"""Pure local checks for the read-only canonical bot DNS/TLS observer."""
import importlib.util
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mojtaba_public_access_readonly",
    ROOT / "scripts/mojtaba_public_access_readonly.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(host, dns, tls):
    return {"host": host, "dns": dns, "tls": tls,
            "https": "not_checked", "status": None}


def test_denies_arbitrary_host_and_private_addresses():
    import pytest
    with pytest.raises(ValueError, match="unregistered"):
        MODULE.probe("localhost")
    assert MODULE._public_ip("127.0.0.1") is False
    assert MODULE._public_ip("10.0.0.1") is False
    assert MODULE._public_ip("::1") is False
    assert MODULE._public_ip("93.184.216.34") is True


def test_total_network_failure_is_unknown_not_fake_target_outage():
    rows = [row(MODULE.TARGET, "unavailable", "not_checked")]
    rows += [row(x, "unavailable", "not_checked") for x in MODULE.REFERENCES]
    summary = MODULE.assess(rows)
    assert summary["reference_dns_functional"] is False
    assert summary["target_public_access"] == "unverified_due_to_observer_network"
    assert summary["subdomain_authority_verified"] is False


def test_verified_tls_does_not_activate_bot_or_merchant():
    rows = [row(MODULE.TARGET, "resolved_public", "verified")]
    rows += [row(x, "resolved_public", "verified") for x in MODULE.REFERENCES]
    summary = MODULE.assess(rows)
    assert summary["target_public_access"] == "tls_endpoint_verified_not_application"
    assert summary["subdomain_authority_verified"] is False
    assert summary["no_payment_or_delivery_verified"] is True
    assert summary["no_production_changes"] is True


def test_target_dns_failure_with_reference_dns_is_not_false_app_claim():
    rows = [row(MODULE.TARGET, "unavailable", "not_checked")]
    rows += [row(MODULE.REFERENCES[0], "resolved_public", "failed")]
    rows += [row(MODULE.REFERENCES[1], "unavailable", "not_checked")]
    summary = MODULE.assess(rows)
    assert summary["reference_dns_functional"] is True
    assert summary["target_public_access"] == "unverified_or_unreachable_from_this_observer"
    assert summary["subdomain_authority_verified"] is False


def test_main_probes_only_exact_three_approved_hosts(capsys):
    with patch.object(MODULE, "probe",
                      side_effect=lambda host: row(host, "unavailable", "not_checked")) as observer:
        MODULE.main()
    import json
    summary = json.loads(capsys.readouterr().out)
    assert observer.call_count == 3
    assert [c.args[0] for c in observer.call_args_list] == list(MODULE.HOSTS)
    assert summary["target"] == "mojtaba.bot.ai"

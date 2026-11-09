"""Offline security and behavior contracts for the direct HTTPS cPanel route."""
from __future__ import annotations

import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "deploy" / "cpanel_https_api_readonly.py"
SPEC = importlib.util.spec_from_file_location("cpanel_https_api_readonly", SOURCE)
assert SPEC and SPEC.loader
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def test_endpoint_and_token_never_enter_the_url():
    token = "unit-test-synthetic-token"
    for operation, endpoint in client.ALLOWED.items():
        req = client.make_request(operation, token)
        assert req.full_url == "https://zohal.pws-dns.net:2083/execute/" + endpoint
        assert req.get_method() == "GET"
        assert token not in req.full_url
        assert req.headers["Authorization"] == "cpanel zomorod2:" + token


def test_unknown_action_rejected_before_any_network_call():
    for operation in ("delete", "Tokens/create_full_access", "../../etc/passwd", "domains?x=1"):
        try:
            client.make_request(operation, "unit-test-synthetic-token")
        except ValueError as exc:
            assert str(exc) == "OPERATION_DENIED"
        else:
            raise AssertionError("Unexpected operation accepted")


def test_redirects_are_not_followed():
    assert client.RefuseRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid/") is None


def test_missing_secret_does_not_attempt_network():
    out, err = io.StringIO(), io.StringIO()
    with patch.dict("os.environ", {client.TOKEN_ENV: ""}), redirect_stdout(out), redirect_stderr(err):
        assert client.main(["client", "domains"]) == 78
    assert out.getvalue() == ""
    assert err.getvalue().strip() == "CPANEL_HTTPS_TOKEN_NOT_CONFIGURED"


def test_success_exposes_only_summary_not_private_domain_values():
    document = {
        "result": {
            "status": 1,
            "data": {
                "main_domain": "private-domain.example",
                "addon_domains": ["another-private.example"],
                "sub_domains": [],
            },
        }
    }
    summary = client.summarize("domains", document)
    assert summary["CPANEL_HTTPS_AUTH"] == "VERIFIED"
    assert summary["MAIN_DOMAIN_PRESENT"] == 1
    assert summary["ADDON_DOMAINS_COUNT"] == 1
    assert "private-domain.example" not in str(summary)


def test_cpanel_failure_never_counts_as_authenticated():
    for status in (None, 0, "0"):
        try:
            client.summarize("domains", {"result": {"status": status, "data": {}}})
        except ValueError:
            pass
        else:
            raise AssertionError("UAPI failure was incorrectly accepted")


def test_invalid_token_characters_rejected():
    for token in ("", "bad\nheader", "bad\rheader", "with space"):
        try:
            client.make_request("domains", token)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid token header accepted")


def test_preflight_performs_only_unauthenticated_https_get():
    response = type("Response", (), {
        "status": 200,
        "__enter__": lambda self: self,
        "__exit__": lambda self, *args: False,
    })()
    with patch.object(client.request, "build_opener") as factory:
        factory.return_value.open.return_value = response
        result = client.probe_transport()
        requests = [call.args[0] for call in factory.return_value.open.call_args_list]
    assert [req.full_url for req in requests] == [
        "https://zohal.pws-dns.net:2083/",
        "https://zohal.pws-dns.net:2083/execute/Version/get",
    ]
    assert all(req.get_method() == "GET" for req in requests)
    assert all("Authorization" not in req.headers for req in requests)
    assert result["CPANEL_HTTPS_TLS"] == "VERIFIED"
    assert result["CPANEL_UAPI_UNAUTH_HTTP_STATUS"] == 200
    assert result["CPANEL_HTTPS_AUTH"] == "NOT_ATTEMPTED"


def test_preflight_reports_unauthenticated_api_challenge_without_claiming_login():
    response = type("Response", (), {
        "status": 200,
        "__enter__": lambda self: self,
        "__exit__": lambda self, *args: False,
    })()
    with patch.object(client.request, "build_opener") as factory:
        factory.return_value.open.side_effect = [response, client.error.HTTPError(
            "https://zohal.pws-dns.net:2083/execute/Version/get", 401,
            "Unauthorized", {}, None,
        )]
        result = client.probe_transport()
    assert result["CPANEL_UAPI_UNAUTH_HTTP_STATUS"] == 401
    assert result["CPANEL_HTTPS_AUTH"] == "NOT_ATTEMPTED"


def test_preflight_does_not_claim_login_without_token():
    out = io.StringIO()
    with patch.dict("os.environ", {client.TOKEN_ENV: ""}), \
            patch.object(client, "probe_transport", return_value={"CPANEL_HTTPS_TLS": "VERIFIED"}), \
            redirect_stdout(out):
        assert client.main(["client", "preflight"]) == 0
    assert "CPANEL_API_TOKEN_STATUS=NOT_CONFIGURED" in out.getvalue()
    assert "CPANEL_HTTPS_AUTH=VERIFIED" not in out.getvalue()

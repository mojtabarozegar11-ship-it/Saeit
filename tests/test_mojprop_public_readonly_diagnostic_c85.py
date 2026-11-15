"""Read-only HTTP000 diagnostics must not turn probes into release or payment.

Source contract for the GitHub runner evidence workflow. No customer requests
are created, no email sent, and no infrastructure is modified in these tests.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
SCANNER = ROOT / "tests/test_tron_merge_trigger_isolation_20261115.py"
CHANGED = (
    ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml",
    "tests/test_mojprop_public_readonly_diagnostic_c85.py",
)


class PublicReachabilityDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKFLOW.read_text(encoding="utf-8")

    def test_readonly_worker_has_no_production_or_customer_write_capabilities(self):
        source = self.content
        self.assertIn("permissions:\n  contents: read", source)
        self.assertIn("runs-on: ubuntu-latest", source)
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("secrets.", source)
        self.assertNotIn("self-hosted", source)
        self.assertNotIn("ssh ", source)
        self.assertNotIn("scp ", source)
        self.assertNotIn("deploy:", source)
        self.assertNotRegex(source, r"(?m)^\s+(?:curl|wget)\s+.*(?:-X\s+POST|--data|--form)")
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true", source)

    def test_five_public_routes_are_read_with_tight_timeouts(self):
        source = self.content
        for path in (
            "https://mojplaywin.com/moj-prop/",
            "https://mojplaywin.com/moj-prop/catalog/",
            "https://mojplaywin.com/moj-prop-intake/",
            "https://mojplaywin.com/moj-prop/signals/",
            "https://mojtaba.bot.ai/",
        ):
            self.assertIn(path, source)
        self.assertIn("--proto '=https'", source)
        self.assertIn("--tlsv1.2", source)
        self.assertIn("--connect-timeout 6 --max-time 15", source)
        self.assertIn("--max-redirs 1", source)

    def test_http000_is_labeled_by_curl_exit_not_claimed_to_be_http_response(self):
        source = self.content
        for marker in (
            "%{http_code}", "%{exitcode}", "%{time_namelookup}",
            "%{time_connect}", "%{time_appconnect}", "%{time_starttransfer}",
            "GET_ONLY_" + chr(36) + "{name}_CURL_EXIT",
            "GET_ONLY_" + chr(36) + "{name}_TRANSPORT_CLASS",
            "dns_resolution_failed", "tcp_connection_failed", "timeout",
            "tls_certificate_or_handshake_failed", "redirect_limit",
            "empty_or_interrupted_response",
        ):
            self.assertIn(marker, source)
        self.assertIn('code="000"', source)
        self.assertIn("PUBLIC_BUYER_ROUTE_GATE=DEGRADED", source)
        self.assertIn("PUBLIC_UNHEALTHY_ROUTE_COUNT=", source)

    def test_probe_does_not_upload_bearer_cookie_or_response_body(self):
        source = self.content
        self.assertIn('$RUNNER_TEMP/mojprop-live-get', source)
        self.assertIn('-o "$check_dir/$name.body"', source)
        self.assertNotIn("upload-artifact", source)
        self.assertNotIn("echo $(cat", source)
        self.assertNotIn("--insecure", source)
        self.assertNotIn("set-cookie", source.lower())

    def test_no_unattended_write_reachable_from_source_change(self):
        assert SCANNER.is_file()
        spec = spec_from_file_location("mojprop_public_probe_c85_scanner", SCANNER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SENSITIVE_SOURCE = CHANGED
        result = module.find_unapproved_release_paths()
        self.assertEqual(result, [], f"Unexpected auto-write trigger: {result[:20]}")


if __name__ == "__main__":
    unittest.main()

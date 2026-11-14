"""Static contractual tests for the existing owner-only cPanel read-only relay."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "deploy/cpanel_direct_command.sh"
WORKFLOW = ROOT / ".github/workflows/cpanel-direct-command-bridge.yml"
SCRIPT = "scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py"


class SourceBridgeContractTests(unittest.TestCase):
    def test_operation_is_allowlisted_once(self):
        source = SHELL.read_text()
        self.assertIn("|mpw_source_provenance)", source)
        self.assertEqual(source.count("|mpw_source_provenance)"), 1)

    def test_operation_available_via_both_existing_pinned_hops(self):
        source = SHELL.read_text()
        self.assertEqual(source.count("  mpw_source_provenance)"), 2)
        self.assertEqual(source.count("< " + SCRIPT), 2)
        self.assertEqual(source.count("PYTHONDONTWRITEBYTECODE=1 python3 -B -"), 2)

    def test_owner_only_main_ref_and_no_fork_workflow(self):
        source = WORKFLOW.read_text()
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("runs-on: [self-hosted, factory-vps]", source)
        self.assertIn("type: choice", source)
        self.assertIn("          - mpw_source_provenance", source)
        self.assertIn("secrets.SAEIT_HOST_SSH_PRIVATE_KEY", source)

    def test_no_unreviewed_dynamic_remote_command_for_new_operation(self):
        src = SHELL.read_text()
        blocks = re.findall(
            r"  mpw_source_provenance\)\n(.*?)\n    ;;", src, re.DOTALL)
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            self.assertIn('ssh -T -F "$work/config" saeit-cpanel', block)
            self.assertIn("python3 -B -", block)
            self.assertIn("< " + SCRIPT, block)
            for forbidden in ("scp ", "rm ", "touch ", "mkdir ", "chmod ",
                              "migrate", "restart", "publish", "payment", "curl "):
                self.assertNotIn(forbidden, block)

    def test_exact_readonly_probe_source_blob_is_pinned_on_both_relay_hops(self):
        import hashlib
        payload = (ROOT / SCRIPT).read_bytes()
        # git hash-object calculates SHA1 of the Git blob header and contents.
        git_blob = b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
        digest = hashlib.sha1(git_blob).hexdigest()
        shell = SHELL.read_text()
        hashes = re.findall(
            r"\$\(git hash-object -- " + re.escape(SCRIPT) +
            r'\)" = "([0-9a-f]{40})"',
            shell,
        )
        self.assertEqual(hashes, [digest, digest])
        self.assertEqual(shell.count("MPW_READONLY_SOURCE_NOT_PINNED"), 2)

    def test_probe_has_no_mutating_or_django_or_network_imports(self):
        content = (ROOT / SCRIPT).read_text()
        self.assertNotIn("import django", content)
        self.assertNotIn("urllib.request", content)
        # Exactly one fixed, bounded, owner-local PassengerApps UAPI lookup
        # is now permitted. Arbitrary subprocess, shell and payment calls
        # remain prohibited and are independently exercised in 54 tests.
        self.assertIn('UAPI_CMD = ("uapi", "--output=json", "PassengerApps", "list_applications")', content)
        self.assertIn("timeout=12, check=False", content)
        self.assertIn("UAPI_OUTPUT_LIMIT = 131_072", content)
        self.assertIn("stderr=DEVNULL", content)
        for banned in ("shell=True", "Popen(", "subprocess.call(",
                       "subprocess.check_output(", "os.popen("):
            self.assertNotIn(banned, content)
        self.assertNotIn("requests.", content)
        self.assertNotIn("os.system", content)
        self.assertNotIn(".write_bytes(", content)
        self.assertNotIn(".write_text(", content)
        self.assertNotIn(".unlink(", content)
        self.assertIn('"files_modified": False', content)

    def test_cpanel_bridge_uses_verified_dns_hostname_not_stale_ip(self):
        source = SHELL.read_text()
        self.assertNotIn("178.239.147.125", source)
        self.assertEqual(source.count("HostName zohal.pws-dns.net"), 2)
        self.assertEqual(source.count("ssh-keyscan -T 10 -p 1396 -t ed25519 zohal.pws-dns.net"), 2)
        self.assertEqual(source.count("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"), 2)

    def test_readonly_bridge_maintains_secure_ssh_properties(self):
        direct = SHELL.read_text()
        self.assertIn("ForwardAgent no", direct)
        self.assertIn("BatchMode yes", direct)
        self.assertIn("StrictHostKeyChecking yes", direct)
        self.assertNotIn("StrictHostKeyChecking no", direct)
        self.assertNotIn("UserKnownHostsFile=/dev/null", direct)

    def test_existing_unknown_operations_still_denied(self):
        src = SHELL.read_text()
        self.assertIn('*) echo "CPANEL_DIRECT_OPERATION_DENIED"', src)
        self.assertIn("StrictHostKeyChecking yes", src)
        self.assertIn("BatchMode yes", src)


if __name__ == "__main__":
    unittest.main()

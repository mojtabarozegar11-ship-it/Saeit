"""Read-only cPanel bridge security regression checks; no remote operations."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/"deploy/cpanel_direct_command.sh"
WORKFLOW=ROOT/".github/workflows/cpanel-direct-command-bridge.yml"
PROBE=ROOT/"scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py"
EXPECTED=("relay_preflight","cpanel_version","passenger_inventory","cpanel_preflight",
          "django_check","django_migrations","zomorod_fields_audit_live",
          "zomorod_fields_verify_stream","mpw_source_provenance")


class DispatchBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sh=SHELL.read_text()
        cls.wf=WORKFLOW.read_text()

    def test_01_shell_syntax_valid(self):
        p=subprocess.run(["bash","-n",str(SHELL)],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_02_exact_operation_allowlist(self):
        lines=[s.strip() for s in self.sh.splitlines() if s.strip().startswith("relay_preflight|")]
        self.assertEqual(len(lines),1)
        self.assertTrue(lines[0].endswith(") ;;"))
        self.assertEqual(tuple(lines[0][:-4].split("|")),EXPECTED)

    def test_03_no_duplicate_operations(self):
        self.assertEqual(len(EXPECTED),len(set(EXPECTED)))

    def test_04_exact_manual_workflow_options(self):
        got=re.findall(r"(?m)^          - ([a-z_]+)$",self.wf)
        self.assertEqual(got,list(EXPECTED[:6])+["mpw_source_provenance"])

    def test_05_choice_input_not_free_text(self):
        self.assertIn("type: choice",self.wf)
        self.assertNotIn("type: string",self.wf)

    def test_06_owner_actor_only(self):
        self.assertIn("github.actor == 'mojtabarozegar11-ship-it'",self.wf)

    def test_07_main_ref_only(self):
        self.assertIn("github.ref == 'refs/heads/main'",self.wf)

    def test_08_exact_repository_only(self):
        self.assertIn("github.repository == 'mojtabarozegar11-ship-it/Saeit'",self.wf)

    def test_09_factory_vps_runner_only(self):
        self.assertIn("runs-on: [self-hosted, factory-vps]",self.wf)

    def test_10_job_timeout(self):
        self.assertIn("timeout-minutes: 8",self.wf)

    def test_11_no_automatic_push_trigger(self):
        self.assertNotIn("\n  push:",self.wf)

    def test_12_no_automatic_pr_trigger(self):
        self.assertNotIn("\n  pull_request:",self.wf)

    def test_13_github_token_read_only(self):
        self.assertIn("permissions:\n  contents: read",self.wf)
        self.assertNotIn("contents: write",self.wf)

    def test_14_git_credentials_not_persisted_on_factory(self):
        self.assertIn("persist-credentials: false",self.wf)

    def test_15_untrusted_operation_not_interpolated_into_script_source(self):
        self.assertIn("OPERATION:",self.wf)
        self.assertIn("inputs.operation",self.wf)
        self.assertIn('bash deploy/cpanel_direct_command.sh "$OPERATION"',self.wf)
        self.assertNotIn('bash deploy/cpanel_direct_command.sh "inputs.operation"',self.wf)

    def test_16_unknown_operation_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as td:
            env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"RUNNER_TEMP":td}
            result=subprocess.run(["bash",str(SHELL),"deploy"],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,64)
            self.assertIn("CPANEL_DIRECT_OPERATION_DENIED",result.stderr)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_17_empty_operation_denied(self):
        with tempfile.TemporaryDirectory() as td:
            env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"RUNNER_TEMP":td}
            result=subprocess.run(["bash",str(SHELL)],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,64)

    def test_18_shell_injection_argument_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as td:
            mark=Path(td)/"injected"
            payload="passenger_inventory; touch "+str(mark)
            env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"RUNNER_TEMP":td}
            result=subprocess.run(["bash",str(SHELL),payload],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,64)
            self.assertFalse(mark.exists())

    def test_19_write_operation_variants_denied(self):
        with tempfile.TemporaryDirectory() as td:
            env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"RUNNER_TEMP":td}
            for word in ("trx_send","invoice_issue","restart","migrate"):
                result=subprocess.run(["bash",str(SHELL),word],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,64,word)

    def test_20_valid_provenance_requires_host_key(self):
        with tempfile.TemporaryDirectory() as td:
            env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"RUNNER_TEMP":td}
            result=subprocess.run(["bash",str(SHELL),"mpw_source_provenance"],
                                  env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("HOST_KEY",result.stderr)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_21_two_pinned_dns_hops(self):
        self.assertEqual(self.sh.count("HostName zohal.pws-dns.net"),2)

    def test_22_stale_host_not_used(self):
        self.assertNotIn("178.239.147.125",self.sh)

    def test_23_two_pinned_cpanel_fingerprints(self):
        self.assertEqual(self.sh.count("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"),2)

    def test_24_ssh_host_checks_strict(self):
        self.assertIn("StrictHostKeyChecking yes",self.sh)
        self.assertNotIn("StrictHostKeyChecking no",self.sh)
        self.assertNotIn("UserKnownHostsFile=/dev/null",self.sh)

    def test_25_agent_forwarding_off(self):
        self.assertIn("ForwardAgent no",self.sh)
        self.assertIn("BatchMode yes",self.sh)

    def test_26_two_bound_immutable_provenance_handlers(self):
        blocks=re.findall(r"(?ms)^ {2,4}mpw_source_provenance\)\n(.*?)\n    ;;",self.sh)
        self.assertEqual(len(blocks),2)
        payload=PROBE.read_bytes()
        digest=hashlib.sha1(b"blob "+str(len(payload)).encode()+b"\x00"+payload).hexdigest()
        for block in blocks:
            self.assertIn(digest,block)
            self.assertIn("python3 -B -",block)
            self.assertIn("PYTHONDONTWRITEBYTECODE=1",block)

    def test_27_no_write_operations_in_provenance_handlers(self):
        blocks=re.findall(r"(?ms)^ {2,4}mpw_source_provenance\)\n(.*?)\n    ;;",self.sh)
        for block in blocks:
            for banned in ("scp ","rsync ","touch ","chmod ","mkdir ","rm ",
                           "restart ","migrate ","curl ","git push","sudo "):
                self.assertNotIn(banned,block)

    def test_28_probe_reports_no_revenue_or_release_proof(self):
        source=PROBE.read_text()
        for field in ('"customer_data_read": False','"database_accessed": False',
                      '"files_modified": False','"production_release_permitted_by_this_report": False'):
            self.assertIn(field,source)

    def test_29_probe_only_allows_fixed_owner_local_readonly_uapi(self):
        source=PROBE.read_text()
        # Local cPanel PassengerApps enumeration is now an explicit narrow
        # dependency. Arbitrary shell commands or customer network I/O remain
        # prohibited; the exact argv and timeout are tested independently.
        self.assertIn('UAPI_CMD = ("uapi", "--output=json", "PassengerApps", "list_applications")',source)
        self.assertIn("timeout=12, check=False",source)
        self.assertIn("UAPI_OUTPUT_LIMIT = 131_072",source)
        for banned in ("import django", "urllib.request", "import requests",
                       "os.system(", "shell=True", "Popen(", "subprocess.call("):
            self.assertNotIn(banned,source)


if __name__=="__main__":
    unittest.main()

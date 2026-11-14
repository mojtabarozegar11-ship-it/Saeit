"""Offline factory attestation trust-boundary checks."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
SH=(R/"scripts/zomorod_cpanel_store_factory_attest_readonly_20261114.sh").read_text()
WF=(R/".github/workflows/zomorod-store-factory-attestation-readonly-20261114.yml").read_text()
GUARD=(R/"scripts/zomorod_cpanel_store_provenance_readonly_20261114.py").read_text()
class Contracts(unittest.TestCase):
 def test_main_only(self):
  self.assertIn("github.ref == 'refs/heads/main'",WF)
 def test_manual_only(self):
  self.assertIn("github.event_name == 'workflow_dispatch'",WF)
 def test_public_pr_job_has_no_secrets(self):
  s=WF.split("  source-contract-tests:")[1].split("  manual-main-factory-attestation:")[0]
  self.assertIn("runs-on: ubuntu-24.04",s)
  self.assertNotIn("secrets.",s)
  self.assertNotIn("self-hosted",s)
 def test_factory_only_on_manual(self):
  self.assertIn("runs-on: [self-hosted, factory-vps]",WF)
  self.assertIn("ref: __D__{{ github.sha }}".replace("__D__","$"),WF)
 def test_shell_rechecks_manual_main(self):
  self.assertIn('test "$GITHUB_REF" = "refs/heads/main"',SH)
  self.assertIn('test "$GITHUB_EVENT_NAME" = "workflow_dispatch"',SH)
 def test_pinned_cpanel_host(self):
  self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",SH)
  self.assertIn("StrictHostKeyChecking=yes",SH)
  self.assertIn("BatchMode=yes",SH)
 def test_direct_existing_factory_route(self):
  self.assertIn("zomorod2@178.239.147.125",SH)
  self.assertNotIn("ProxyJump",SH)
  self.assertNotIn("178.239.147.150",SH)
 def test_key_lifetime(self):
  self.assertIn("umask 077",SH)
  self.assertIn("chmod 600",SH)
  self.assertIn("trap 'rm -rf --",SH)
  self.assertNotIn("set -x",SH)
 def test_guard_stream_only(self):
  self.assertIn("< scripts/zomorod_cpanel_store_provenance_readonly_20261114.py",SH)
  self.assertIn("bounded_regular_file",GUARD)
  for cmd in ("scp ","rsync ","sudo ","chmod 777"):
   self.assertNotIn(cmd,SH)
 def test_private_module_hash_not_exposed(self):
  self.assertNotIn('remote["private_store_module_sha256"]',SH)
  self.assertIn('"private_module_read_but_not_disclosed":True',SH)
 def test_no_http_parity_claim(self):
  self.assertIn('assert remote["verified_public_http_serving_parity"] is False',SH)
  self.assertIn('"verified_public_http_serving_parity":False',SH)
 def test_no_auto_deploy(self):
  self.assertIn("  workflow_dispatch:",WF)
  self.assertIn("  pull_request:",WF)
  self.assertNotIn("  push:",WF)
  self.assertNotIn("  schedule:",WF)
 def test_evidence_limited(self):
  self.assertIn("zm-factory-store-source.jsonl",WF)
  self.assertNotIn("remote.json",WF)
  self.assertIn("retention-days: 7",WF)
if __name__=="__main__":
 unittest.main()

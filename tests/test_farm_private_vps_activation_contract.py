"""Review contract for the strictly private, fail-closed one-product VPS activation."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "activate_farm_v2_private_20261107.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "vps-farm-v2-private-activation-20261107.yml"


class PrivateFarmV2ActivationContract(unittest.TestCase):
    def test_shell_parses_and_rejects_local_non_service_user_before_changes(self):
        syntax = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run(["bash", str(SCRIPT), "/tmp/unsafe", "not-a-sha"],
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FARM_V2_WRONG_SERVICE_USER", result.stdout)

    def test_preflight_locks_rollback_and_private_publication_boundary(self):
        source = SCRIPT.read_text(encoding="utf8")
        for required in (
            '[[ "$(id -un)" == githubops',
            'FARM_V2_LOW_STORAGE_RESERVE_HOLD',
            'FARM_V2_SINGLE_PRODUCT_CRON_NOT_PROVEN',
            'flock -w 100 9',
            'flock -w 30 8',
            'trap restore_on_error EXIT',
            'cp -a -- "$backup/source-before" "$installed"',
            'cp -a -- "$backup/product-before" "$private_product"',
            '"$expected_zip"',
            'private_internal_qa_pass_not_published',
            'commercial_release_permitted_from_manufacturing',
            'FARM_V2_PUBLICATION_ENABLED=false',
        ):
            self.assertIn(required, source)
        self.assertNotIn('crontab -', source.replace('crontab -l', ''))
        self.assertNotIn('/home/zomorod2', source)
        self.assertNotIn('authorize-publication', source)

    def test_workflow_never_activates_on_pull_requests(self):
        workflow = WORKFLOW.read_text(encoding="utf8")
        self.assertIn('pull_request:', workflow)
        self.assertIn('github.event_name == \'push\'', workflow)
        self.assertIn('refs/heads/main', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('StrictHostKeyChecking yes', workflow)
        self.assertIn('SAEIT_SINGLE_PRODUCT_FACTORY_V1', SCRIPT.read_text(encoding='utf8'))


if __name__ == "__main__":
    unittest.main()

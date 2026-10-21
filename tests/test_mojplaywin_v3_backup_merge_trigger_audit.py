"""Static workflow push-trigger guard fixtures; no GitHub operations."""
import unittest
from scripts import mojplaywin_v3_backup_merge_trigger_audit as audit


class MergeWorkflowTriggerContract(unittest.TestCase):
    def test_no_push(self):
        self.assertEqual(audit.event("on:\n  pull_request:\n  workflow_dispatch:\n")[0], "none")

    def test_no_main(self):
        self.assertEqual(audit.event("on:\n  push:\n    branches: [dev]\n")[0], "none")

    def test_main_and_unfiltered(self):
        self.assertEqual(audit.event("on:\n  push:\n    branches: [main]\n")[0], "push_all")

    def test_main_exact_workflow_path_matches(self):
        text = ("on:\n  push:\n    branches: [main]\n    paths:\n"
                "      - 'scripts/mojplaywin_backup_encrypt_vps_gpg.py'\n"
                "permissions:\n  contents: read\n")
        kind, hits = audit.event(text)
        self.assertEqual(kind, "push_matching")
        self.assertIn("scripts/mojplaywin_backup_encrypt_vps_gpg.py", hits)

    def test_branch_scoped_test_job_not_tripped(self):
        text = ("on:\n  push:\n    branches: [fix/mpw-gzip-before-ssh-backup-20261020]\n"
                "    paths: ['scripts/mojplaywin_backup_encrypt_vps_gpg.py']\n")
        self.assertEqual(audit.event(text)[0], "none")

    def test_unrelated_path_is_not_released(self):
        self.assertEqual(audit.event("on:\n  push:\n    branches: [main]\n"
                                     "    paths: ['core/templates/mojplaywin/**']\n")[0], "none")

    def test_wildcard_release_is_flagged(self):
        self.assertEqual(audit.event("on:\n  push:\n    paths: ['scripts/**']\n")[0], "push_matching")

    def test_ambiguous_yaml_not_silently_allowed(self):
        self.assertEqual(audit.event("name: unspecified\njobs:\n  test:\n")[0], "unknown")


if __name__ == "__main__":
    unittest.main()

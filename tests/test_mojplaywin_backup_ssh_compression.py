"""Protect the opt-in encrypted backup's pinned and compressed SSH transport."""
from pathlib import Path
import unittest

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/mojplaywin-encrypted-backup-gpg-v2-20261017.yml"
)


class MojPlayWinBackupTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_exactly_two_bulk_ssh_legs_use_transport_compression(self):
        for host in ("saeit-cpanel", "saeit-vps"):
            command = 'timeout 1300s ssh -C -T -F "$d/config" ' + host
            self.assertEqual(self.workflow.count(command), 1)
            self.assertNotIn('timeout 1300s ssh -T -F "$d/config" ' + host,
                             self.workflow)

    def test_owner_approval_and_host_identity_guards_remain(self):
        self.assertIn(
            "startsWith(github.event.head_commit.message, "
            "'[approved-backup-gpg-v2-20261017]')",
            self.workflow,
        )
        self.assertIn("StrictHostKeyChecking yes", self.workflow)
        self.assertIn("ProxyJump saeit-vps", self.workflow)
        self.assertIn("SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs",
                      self.workflow)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",
                      self.workflow)


if __name__ == "__main__":
    unittest.main()

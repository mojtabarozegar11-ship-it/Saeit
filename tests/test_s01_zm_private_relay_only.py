"""Prevent alternate SSH ingress and live writes in Zomorod private staging."""
from pathlib import Path
import unittest

WORKFLOW = (Path(__file__).resolve().parents[1] / ".github/workflows" /
            "zomorod-messaging-private-staging.yml").read_text(encoding="utf-8")


class PrivateRelayContractTests(unittest.TestCase):
    def test_relay_is_the_only_ssh_transport(self):
        self.assertIn("ProxyJump saeit-vps", WORKFLOW)
        self.assertIn("StrictHostKeyChecking yes", WORKFLOW)
        self.assertNotIn("saeit-cpanel-direct", WORKFLOW)
        self.assertNotIn("ProxyJump none", WORKFLOW)
        self.assertIn("case \"$COMMAND_HOST\" in saeit-cpanel) ;; *) exit 1 ;; esac", WORKFLOW)

    def test_no_live_deployment(self):
        self.assertIn("PRIVATE_STAGE_NO_DEPLOY", WORKFLOW)
        self.assertIn("PRODUCTION_FILES_CHANGED=false", WORKFLOW)
        self.assertIn("PRODUCTION_SCHEMA_UNMODIFIED=true", WORKFLOW)

    def test_staging_database_is_separate_and_sending_disabled(self):
        self.assertIn('DATABASE_URL="sqlite:///$root/isolation.sqlite3"', WORKFLOW)
        self.assertIn("COMPANY_MESSAGING_SEND_ENABLED=false", WORKFLOW)
        self.assertIn("COMPANY_MARKETING_PUBLISH_ENABLED=false", WORKFLOW)
        self.assertIn("ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=false", WORKFLOW)

    def test_staging_collectstatic_does_not_touch_live(self):
        self.assertIn('isolated_root=pathlib.Path.cwd()/".static-preflight"', WORKFLOW)
        self.assertIn('assert (isolated_root/"staticfiles.json").is_file()', WORKFLOW)


if __name__ == "__main__":
    unittest.main()

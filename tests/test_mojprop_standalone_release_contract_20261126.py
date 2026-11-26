import unittest

from scripts.mojprop_standalone_release_contract import evaluate


class MojPropReleaseContractTests(unittest.TestCase):
    def test_missing_configuration_is_blocked(self):
        result = evaluate({})
        self.assertFalse(result["ready"])
        self.assertIn("MOJPROP_DOCROOT is missing", " ".join(result["blockers"]))

    def test_legacy_root_is_blocked(self):
        result = evaluate({
            "MOJPROP_DOCROOT": "/home/zomorod2/mojplaywin.com",
            "MOJPROP_RELEASE_APPROVED": "true",
            "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED": "true",
            "MOJPROP_TENANT_ISOLATION_VERIFIED": "true",
            "MOJPROP_ROLLBACK_VERIFIED": "true",
        })
        self.assertFalse(result["ready"])
        self.assertIn("must not contain mojplaywin", " ".join(result["blockers"]))

    def test_complete_explicit_contract_is_ready_for_external_preflight_only(self):
        result = evaluate({
            "MOJPROP_DOCROOT": "/home/zomorod2/mojprop.top",
            "MOJPROP_RELEASE_APPROVED": "true",
            "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED": "true",
            "MOJPROP_TENANT_ISOLATION_VERIFIED": "true",
            "MOJPROP_ROLLBACK_VERIFIED": "true",
        })
        self.assertTrue(result["ready"])
        self.assertEqual(result["host"], "mojprop.top")

"""Synthetic only. Never connect to cPanel during tests."""
import unittest

from scripts.mojplaywin_cpanel_domains_backups_readonly import (
    summary_domains, summary_backups
)


class ReadonlyCpanelDomainBackupTests(unittest.TestCase):
    def test_private_unlisted_domains_never_print(self):
        doc={"result":{"status":1,"data":{
            "main_domain":"example.co",
            "addon_domains":["mojplaywin.com","sensitive-private.example.org"],
            "parked_domains":[],
            "sub_domains":["dev.mojplaywin.com","secret.sensitive-private.example.org"]}}}
        got=summary_domains(doc)
        self.assertTrue(got["main_mojplaywin_domain_listed"])
        self.assertEqual(got["mojplaywin_subdomain_count"],1)
        self.assertNotIn("sensitive-private",str(got))
        self.assertFalse(got["release_permitted"])
        self.assertTrue(got["path_based_child_sites_not_enumerated"])

    def test_backup_entries_redacted_and_not_proven_restorable(self):
        doc={"result":{"status":1,"data":[
            {"file":"/home/example/backup_secret.tar.gz","status":"complete"},
            {"file":"another-private-archive","status":"in_progress"}]}}
        got=summary_backups(doc)
        self.assertEqual(got["api_list_entry_count"],2)
        self.assertEqual(got["reported_status_counts"]["complete"],1)
        self.assertNotIn("backup_secret",str(got))
        self.assertFalse(got["full_database_and_media_backup_verified"])
        self.assertFalse(got["restore_test_verified"])

    def test_empty_uapi_backup_list_does_not_prove_absence_of_backups(self):
        got=summary_backups({"result":{"status":1,"data":[]}})
        self.assertEqual(got["api_list_entry_count"],0)
        self.assertTrue(got["api_can_omit_offsite_or_nonstandard_backups"])
        self.assertFalse(got["release_permitted"])

    def test_bad_api_fails_closed(self):
        for data in ({"result":{"status":0,"data":[]}},{"result":{"status":1,"data":None}}):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    summary_backups(data)


if __name__ == "__main__":
    unittest.main()

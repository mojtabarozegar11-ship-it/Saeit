import unittest
from scripts.mpw_store_backup_boundary_readonly_20261119 import boundary, quota_fields, account_quota_fields

class StoreBackupBoundaryTests(unittest.TestCase):
    def test_transitive_parents_and_cycles(self):
        tables = {k: ("InnoDB", n) for k,n in (("invoice",10),("buyer",20),("profile",30),("other",40))}
        r = boundary({"invoice"}, tables, {("invoice","buyer"),("buyer","profile"),("profile","buyer"),("other","buyer")})
        self.assertEqual(r["required_table_count"],3)
        self.assertEqual(r["additional_required_tables"],2)
        self.assertEqual(r["estimated_required_table_bytes"],60)
        self.assertEqual(r["incoming_boundary_edges"],1)
        self.assertFalse(r["row_scope_proven"])
    def test_missing_and_cross_schema_parents_fail_closed(self):
        r = boundary({"invoice","missing"}, {"invoice":("MyISAM",7)}, {("invoice",None),("invoice","absent")})
        self.assertEqual(r["seed_tables_missing"],1)
        self.assertEqual(r["missing_parent_edges"],2)
        self.assertFalse(r["required_tables_transactional"])
    def test_empty_scope_is_not_transactional(self):
        self.assertFalse(boundary({"missing"},{},set())["required_tables_transactional"])
    def test_quota_is_local_and_never_total(self):
        d = {"module":"Quota","func":"get_local_quota_info","result":{"status":1,"errors":None,"data":{
            "bytes_used":110,"byte_limit":100,"inodes_used":2,"inode_limit":10}}}
        q = quota_fields(d)
        self.assertEqual(q["local_byte_headroom"],0)
        self.assertEqual(q["local_inode_headroom"],8)
        self.assertFalse(q["account_total_quota_proven"])
        d["result"]["data"]["byte_limit"] = 0
        self.assertIsNone(quota_fields(d)["local_byte_headroom"])
    def test_quota_rejects_ambiguous_types_and_errors(self):
        d = {"module":"Quota","func":"get_local_quota_info","result":{"status":1,"data":{
            "bytes_used":"2","byte_limit":100,"inodes_used":2,"inode_limit":10}}}
        with self.assertRaises(ValueError):
            quota_fields(d)
        d["result"]["data"]["bytes_used"] = 2
        d["result"]["errors"] = ["failed"]
        with self.assertRaises(ValueError):
            quota_fields(d)

    def account_document(self):
        return {"module":"Quota","func":"get_quota_info","result":{"status":1,"data":{
            "megabyte_limit":40960,"megabytes_used":40000.5,"megabytes_remain":950.25,
            "inode_limit":100000,"inodes_used":75000,"inodes_remain":24000,
            "under_megabyte_limit":1,"under_inode_limit":1,"under_quota_overall":1}}}
    def test_account_quota_conservative_headroom(self):
        q = account_quota_fields(self.account_document())
        self.assertEqual(q["account_disk_headroom_reported_mb"],950.25)
        self.assertEqual(q["account_inode_headroom_reported"],24000)
        self.assertTrue(q["account_total_quota_observed"])
        self.assertFalse(q["backup_capacity_proven"])
    def test_account_zero_limit_does_not_prove_free_space(self):
        d = self.account_document()
        d["result"]["data"]["megabyte_limit"] = 0
        d["result"]["data"]["inode_limit"] = 0
        q = account_quota_fields(d)
        self.assertIsNone(q["account_disk_headroom_reported_mb"])
        self.assertIsNone(q["account_inode_headroom_reported"])
    def test_account_over_quota_clamps_headroom(self):
        d = self.account_document()
        d["result"]["data"]["megabytes_used"] = 42000
        d["result"]["data"]["under_megabyte_limit"] = 0
        d["result"]["data"]["under_quota_overall"] = 0
        self.assertEqual(account_quota_fields(d)["account_disk_headroom_reported_mb"],0)
    def test_account_rejects_untrusted_response(self):
        for field,value in (("megabytes_used",float("nan")),("megabytes_remain",True),
                            ("under_quota_overall","1"),("inodes_used",-1)):
            with self.subTest(field=field):
                d=self.account_document()
                d["result"]["data"][field]=value
                with self.assertRaises(ValueError):
                    account_quota_fields(d)
        d=self.account_document()
        d["result"]["warnings"]=["stale"]
        with self.assertRaises(ValueError):
            account_quota_fields(d)
    def test_account_local_response_not_interchangeable(self):
        with self.assertRaises(ValueError):
            quota_fields(self.account_document())

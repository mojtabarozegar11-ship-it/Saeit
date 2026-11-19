import unittest
from scripts.mpw_store_backup_boundary_readonly_20261119 import boundary, quota_fields

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

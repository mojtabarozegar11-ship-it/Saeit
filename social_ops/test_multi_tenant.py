import unittest
from datetime import datetime, timezone
from multi_tenant import plan, validate

class MultiTenantTests(unittest.TestCase):
 def test_capacity(self):
  validate({"tenants":[{"id":f"tenant_{i}","destinations":[]} for i in range(50)]})
  with self.assertRaises(ValueError):
   validate({"tenants":[{"id":f"tenant_{i}","destinations":[]} for i in range(51)]})
 def test_isolation_and_permissions(self):
  r={"tenants":[{"id":"a","destinations":[{"id":"ig","network":"instagram","account_ref":"a","enabled":True,"authorized":True}]},{"id":"b","destinations":[{"id":"fb","network":"facebook","account_ref":"b","enabled":False,"authorized":True}]}]}
  d={"a":{"brand":"a","id":"post1","text":"hello","approved":True,"media":["https://example.org/a.jpg"]},"b":{"brand":"b","id":"post2","text":"hello","approved":True}}
  jobs=plan(r,d,datetime(2026,10,9,tzinfo=timezone.utc))
  self.assertEqual(len(jobs),1)
  self.assertEqual(jobs[0]["tenant_id"],"a")
  self.assertEqual(jobs[0]["status"],"pending_dispatch")
 def test_fail_closed(self):
  r={"tenants":[{"id":"a","destinations":[{"id":"fb","network":"facebook","account_ref":"a","enabled":True,"authorized":True}]}]}
  self.assertEqual(plan(r,{"a":{"brand":"a","id":"1","text":"hello","approved":False}}),[])

if __name__ == "__main__":
 unittest.main()

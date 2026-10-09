import unittest
from datetime import date
from agent import build

class AgentTests(unittest.TestCase):
 def test_isolation_and_safety(self):
  drafts = build(date(2026, 10, 9))
  self.assertEqual(set(drafts), {"personal", "company", "vancouver_personal"})
  self.assertEqual(len({d["id"] for d in drafts.values()}), 3)
  self.assertTrue(all(d["status"] == "draft_requires_review" and not d["approved"] and not d["auto_publish"] for d in drafts.values()))
 def test_deterministic(self):
  self.assertEqual(build(date(2026, 10, 9)), build(date(2026, 10, 9)))

if __name__ == "__main__":
 unittest.main()

import unittest
from editorial_briefs import build_briefs
class BriefTests(unittest.TestCase):
 def test_missing(self):
  self.assertEqual(build_briefs({"ranked":[]})["company"]["status"],"research_insufficient")
 def test_relevance(self):
  r=build_briefs({"ranked":[{"title":"Agriculture research","url":"https://example.org/a","source_url":"https://example.org/a"}]})
  self.assertEqual(r["company"]["status"],"research_ready_for_editorial_review")
  self.assertFalse(r["company"]["can_publish"])
if __name__=="__main__":
 unittest.main()

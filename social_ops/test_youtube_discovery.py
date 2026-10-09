import unittest
from youtube_discovery import normalize, collect
class DiscoveryTests(unittest.TestCase):
 def test_no_key(self):
  posts,state=collect("")
  self.assertEqual(posts,[])
  self.assertEqual(state["status"],"not_configured")
 def test_normalize(self):
  result=normalize({"items":[{"id":"abc123","snippet":{"publishedAt":"2026-10-08T10:00:00Z","title":"Example"},"statistics":{"viewCount":"100","likeCount":"5"}}]},"CA","2026-10-09T00:00:00Z")
  self.assertEqual(result[0]["views"],100)
  self.assertIsNone(result[0]["comments"])
if __name__=="__main__":
 unittest.main()

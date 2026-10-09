import unittest
from datetime import datetime, timezone
from research import evaluate

NOW = datetime(2026,10,9,tzinfo=timezone.utc)
class ResearchTests(unittest.TestCase):
 def test_no_evidence(self):
  self.assertEqual(evaluate([],NOW),[])
 def test_verified_fields_and_ranking(self):
  base={"platform":"youtube","url":"https://youtube.com/watch?v=123","source_url":"https://youtube.com/watch?v=123","published_at":"2026-10-08T00:00:00Z","views":1000,"likes":100,"comments":10,"shares":5}
  result=evaluate([base],NOW)
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]["engagement"],115)
 def test_reject_unsupported_or_unverifiable(self):
  self.assertEqual(evaluate([{"platform":"youtube","url":"http://example.com"}],NOW),[])
if __name__=="__main__":
 unittest.main()

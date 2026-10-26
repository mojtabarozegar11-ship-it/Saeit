"""No-API-key, no-network contract checks for opt-in ChatGPT drafting."""
import json
import unittest
from social_hub.ai import propose
from social_hub.adapters import Response, Blocked, Uncertain

BRIEF = "Original farm operations research briefing from the owner; summarize strictly these facts."

class AICopywriterTests(unittest.TestCase):
    def test_consent_and_key_are_required_without_external_io(self):
        calls=[]
        def fake(*args):
            calls.append(args)
            raise AssertionError("Must not call a network")
        with self.assertRaises(Blocked):
            propose(brief=BRIEF,brand="personal",platforms=["telegram"],
                    env={},transport=fake)
        with self.assertRaises(Blocked):
            propose(brief=BRIEF,brand="personal",platforms=["telegram"],
                    explicit_api_consent=True,env={},transport=fake)
        self.assertEqual(len(calls),0)

    def test_completed_api_response_only_generates_review_draft(self):
        calls=[]
        obj={"variants":[{"platform":"telegram","text":"A factual draft for review","notes":"Check claims"}],
             "claims_to_verify":["Any statistics"]}
        response={"status":"completed","output":[{"content":[{"type":"output_text",
                    "text":json.dumps(obj)}]}]}
        def fake(method,url,body,headers):
            calls.append((method,url,body,headers))
            return Response(200,response,{})
        out=propose(brief=BRIEF,brand="personal",platforms=["telegram"],
            explicit_api_consent=True,env={"MPW_SOCIAL_OPENAI_API_KEY":"sk-"+"a"*35},
            transport=fake)
        self.assertFalse(out["published"])
        self.assertTrue(out["human_approval_required"])
        self.assertEqual(len(out["variants"]),1)
        self.assertEqual(calls[0][1],"https://api.openai.com/v1/responses")
        self.assertFalse(calls[0][2]["store"])
        self.assertEqual(calls[0][2]["text"]["format"]["type"],"json_schema")

    def test_block_forbidden_accounts_and_wrong_platform(self):
        def fake(method,url,body,headers):
            obj={"variants":[{"platform":"x","text":"Post","notes":""}],"claims_to_verify":[]}
            return Response(200,{"status":"completed","output":[{"content":[{"type":"output_text","text":json.dumps(obj)}]}]}, {})
        with self.assertRaises(Blocked):
            propose(brief="Please promote dr.mojtaba.rozegar in a professional farm post",
                brand="personal",platforms=["telegram"],explicit_api_consent=True,
                env={"MPW_SOCIAL_OPENAI_API_KEY":"sk-"+"a"*35},transport=fake)
        with self.assertRaises(Uncertain):
            propose(brief=BRIEF,brand="personal",platforms=["telegram"],
                explicit_api_consent=True,
                env={"MPW_SOCIAL_OPENAI_API_KEY":"sk-"+"a"*35},transport=fake)

if __name__=="__main__":
    unittest.main()

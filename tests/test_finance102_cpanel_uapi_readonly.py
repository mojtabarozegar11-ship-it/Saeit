"""Mock-only cPanel UAPI; no live token or network is touched."""
import json
import unittest
from scripts.finance102_cpanel_uapi_readonly import API_URL, classify, run

class FakeResponse:
    status=200
    headers={"Content-Type":"application/json; charset=utf-8"}
    def __init__(self, data): self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,limit):return json.dumps(self.data).encode("utf8")[:limit]

class FakeOpener:
    def __init__(self, data): self.data=data;self.req=None
    def open(self,request,timeout):
        self.req=request
        assert timeout==15
        return FakeResponse(self.data)

class Tests(unittest.TestCase):
    def test_readonly_api_endpoint_and_no_upload(self):
        self.assertEqual(API_URL,"https://zohal.pws-dns.net:2083/execute/PassengerApps/list_applications")
        self.assertNotIn("upload",API_URL)
    def test_complete_authenticated_mapping(self):
        appdata={"status":1,"errors":None,"messages":None,"metadata":{},
                 "data":[{"domain":"zomorodmelal.ir","base_uri":"/","path":"/home/zomorod2/Saeit"},
                         {"domain":"mojplaywin.com","base_uri":"/","path":"/home/zomorod2/Saeit-staging"}]}
        opener=FakeOpener({"result":appdata})
        self.assertEqual(run("T"*20, opener),{"zomorodmelal.ir":True,"mojplaywin.com":True})
        self.assertEqual(opener.req.get_method(),"GET")
        self.assertEqual(opener.req.full_url,API_URL)
    def test_no_auth_or_incomplete_mapping(self):
        with self.assertRaises(ValueError):run(None,FakeOpener({}))
        data={"status":1,"errors":None,"messages":None,"metadata":{},"data":[]}
        self.assertFalse(all(classify(data).values()))
        data["data"]=[{"domain":"zomorodmelal.ir","base_uri":"/","path":"/home/zomorod2/Saeit"}]*2
        self.assertFalse(classify(data)["zomorodmelal.ir"])
    def test_denied_and_wrong_shape_fail_closed(self):
        for status in (0,None):
            with self.assertRaises(ValueError):
                classify({"status":status,"errors":["bad"],"messages":None,"metadata":{},"data":[]})
        with self.assertRaises(ValueError):classify({"status":1})
        with self.assertRaises(ValueError):run("T"*20,FakeOpener({"error":"login required"}))

if __name__=="__main__":unittest.main()

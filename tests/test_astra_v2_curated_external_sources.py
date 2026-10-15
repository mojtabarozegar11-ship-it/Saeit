"""No-network tests of five-source public research availability observations."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_v2_curated_external_sources.py"
spec=importlib.util.spec_from_file_location("astra_curated_sources",SCRIPT)
monitor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class FakeReply:
    status=200
    headers={"Content-Type":"text/html; charset=utf-8"}
    def __init__(self,body=b"<html><title>University research guide</title></html>"):
        self.body=body
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,size): return self.body[:size]


class FakeOpener:
    def __init__(self,responses=None):
        self.responses=responses or {}
        self.requests=[]
    def open(self,request,timeout=None):
        self.requests.append((request.full_url,timeout))
        result=self.responses.get(request.full_url)
        if isinstance(result,BaseException): raise result
        return result or FakeReply()


class CuratedSourceTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.folder=Path(t.name)/"private"
        self.folder.mkdir(mode=0o700)
        self.path=self.folder/"official-sources.json"

    def test_exact_five_sources_and_one_internal_guard(self):
        opener=FakeOpener()
        result=monitor.run(self.path,opener=opener)
        self.assertEqual(result["attempted"],5)
        self.assertEqual(result["retrieved_unverified"],5)
        self.assertEqual(result["number_of_salable_products_created"],0)
        self.assertEqual(len(opener.requests),5)
        self.assertTrue(all(t==10 for _,t in opener.requests))
        data=json.loads(self.path.read_text())
        self.assertEqual(data["internal_audit"]["retail_release_authorized"],False)
        self.assertFalse(data["internal_audit"]["real_buyer_demand_attested"])
        self.assertFalse(data["source_article_text_saved"])
        self.assertNotIn("<html>",self.path.read_text())

    def test_http_403_counts_as_blocked_not_evidence(self):
        url=monitor.SOURCES[0][1]
        obj=FakeOpener({url:HTTPError(url,403,"Forbidden",{},None)})
        r=monitor.run(self.path,opener=obj)
        self.assertEqual(r["retrieved_unverified"],4)
        self.assertEqual(r["failed_or_inaccessible"],1)
        self.assertEqual(json.loads(self.path.read_text())["external_observations"][0]["transport_state"],"HTTP_ERROR")

    def test_network_failure_is_recorded_without_fake_success(self):
        url=monitor.SOURCES[-1][1]
        obj=FakeOpener({url:URLError("DNS unavailable")})
        r=monitor.run(self.path,opener=obj)
        self.assertEqual(r["failed_or_inaccessible"],1)
        self.assertFalse(r["real_buyer_demand_attested"])

    def test_strict_redirect_handling(self):
        self.assertIsNone(monitor.NoRedirect().redirect_request(
            None,None,301,"Moved",{},"https://evil.example/"))

    def test_unknown_targets_blocked(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_SOURCE_NOT_ALLOWED"):
            monitor.run(self.path,opener=FakeOpener(),sources=monitor.SOURCES[:4]+(("extra","https://example.com","unknown"),])

    def test_short_bounded_hash_and_no_republished_text(self):
        url=monitor.SOURCES[0][1]
        body=b"A"*(monitor.MAX_RESPONSE_BYTES+400)
        monitor.run(self.path,opener=FakeOpener({url:FakeReply(body)}))
        data=json.loads(self.path.read_text())
        row=data["external_observations"][0]
        self.assertTrue(row["body_is_truncated_or_partial"])
        self.assertEqual(row["bounded_bytes_observed"],monitor.MAX_RESPONSE_BYTES)
        self.assertEqual(len(row["content_prefix_sha256"]),64)
        self.assertNotIn("AAAAAA",self.path.read_text())

    def test_source_check_rejects_forged_demand(self):
        monitor.run(self.path,opener=FakeOpener())
        payload=json.loads(self.path.read_text())
        payload["external_observations"][0]["demand_verified"]=True
        self.path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_FABRICATED_VERIFICATION"):
            monitor.verify(self.path)

    def test_check_requires_matching_allowlist(self):
        monitor.run(self.path,opener=FakeOpener())
        payload=json.loads(self.path.read_text())
        payload["external_observations"][1]["url"]="https://malicious.example/"
        self.path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_SOURCE_MISMATCH"):
            monitor.verify(self.path)

    def test_check_success_never_claims_sale(self):
        monitor.run(self.path,opener=FakeOpener())
        r=monitor.verify(self.path)
        self.assertEqual(r["sources"],5)
        self.assertFalse(r["sale_ready"])

    def test_no_symlink_output(self):
        target=self.folder/"valuable.json"
        target.write_text("original")
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError,"OUTPUT_PATH_NOT_PRIVATE"):
            monitor.run(self.path,opener=FakeOpener())
        self.assertEqual(target.read_text(),"original")

    def test_directory_permissions_enforced(self):
        self.folder.chmod(0o755)
        with self.assertRaisesRegex(ValueError,"OUTPUT_DIRECTORY_NOT_PRIVATE"):
            monitor.run(self.path,opener=FakeOpener())


if __name__=="__main__":
    unittest.main()

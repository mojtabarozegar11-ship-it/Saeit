"""Offline-only regressions: cPanel UAPI HTTPS, authorization and privacy."""
import hashlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import mpw_cpanel_uapi_https_revenue_readonly as u

TOKEN="MOCK_ONLY_TEST_TOKEN_NO_PRIVILEGES"

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload=payload
        self.status=status
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def getcode(self):return self.status
    def read(self,n=-1):return self.payload[:n]

class FakeOpener:
    def __init__(self, payload):self.payload=payload;self.last=None
    def open(self,req,timeout=12):
        self.last=req
        return FakeResponse(self.payload)

def good(data):
    return json.dumps({"result":{"status":1,"data":data}}).encode()

class UapiHttpsTests(unittest.TestCase):
    def test_01_exact_https_port2083(self):
        self.assertEqual(u.CPANEL_BASE,"https://zohal.pws-dns.net:2083/execute/")
    def test_02_empty_token_never_networks(self):
        with patch.object(u,"_request",side_effect=RuntimeError("called")):
            self.assertEqual(u.run("")["status"],"no_existing_authorized_token")
    def test_03_valid_whitelisted_passenger(self):
        op=FakeOpener(good([]))
        self.assertEqual(u._request("PassengerApps","list_applications",{},TOKEN,opener=op),[])
    def test_04_send_only_get(self):
        op=FakeOpener(good([]))
        u._request("PassengerApps","list_applications",{},TOKEN,opener=op)
        self.assertEqual(op.last.get_method(),"GET")
    def test_05_allowlist_blocks_mutating_function(self):
        with self.assertRaises(ValueError):
            u._request("Fileman","delete_file",{},TOKEN,opener=FakeOpener(good([])))
    def test_06_blocks_lead_content_read(self):
        with self.assertRaises(ValueError):
            u._request("Fileman","get_file_content",{},TOKEN,opener=FakeOpener(good([])))
    def test_07_rejects_nonwhitelisted_path(self):
        with self.assertRaises(ValueError):
            u._request("Fileman","list_files",{"dir":"/etc"},TOKEN,opener=FakeOpener(good([])))
    def test_08_rejects_changed_account_domain(self):
        with self.assertRaises(ValueError):
            u._request("Email","list_pops",{"domain":"other.com"},TOKEN,opener=FakeOpener(good([])))
    def test_09_invalid_key_short(self):
        with self.assertRaises(ValueError):
            u._request("PassengerApps","list_applications",{},"tiny",opener=FakeOpener(good([])))
    def test_10_invalid_key_newline(self):
        with self.assertRaises(ValueError):
            u._request("PassengerApps","list_applications",{},TOKEN+"\n",opener=FakeOpener(good([])))
    def test_11_do_not_follow_http_redirect(self):
        handler=u._NoRedirect()
        self.assertIsNone(handler.redirect_request(None,None,302,"moved",{},"https://evil.example/"))
    def test_12_bad_uapi_result_is_not_success(self):
        with self.assertRaises(ValueError):
            u._request("PassengerApps","list_applications",{},TOKEN,opener=FakeOpener(b'{"result":{"status":0,"data":[]}}'))
    def test_13_malformed_json_is_rejected(self):
        with self.assertRaises(ValueError):
            u._request("PassengerApps","list_applications",{},TOKEN,opener=FakeOpener(b"{garbled"))
    def test_14_large_reply_refused(self):
        with self.assertRaises(ValueError):
            u._request("PassengerApps","list_applications",{},TOKEN,opener=FakeOpener(b" "* (u.MAX_BYTES+1)))
    def test_15_url_encoded_private_directory(self):
        op=FakeOpener(good([]))
        u._request("Fileman","list_files",{"dir":u.PRIVATE_DIR,"show_hidden":"1"},TOKEN,opener=op)
        self.assertIn("%2Fhome%2Fzomorod2",op.last.full_url)
        self.assertNotIn("?",op.last.full_url.split("/execute/")[0])
    def test_16_email_has_no_raw_recipients_in_summary(self):
        a=u._mail_summary([{"email":"support@mojplaywin.com"},{"email":"secret@mojplaywin.com"}])
        self.assertTrue(a["support_mailbox_configured"])
        self.assertNotIn("secret@mojplaywin.com",str(a))
    def test_17_passenger_summary_no_app_paths(self):
        a=u._passenger_summary([{"name":"sensitive_private_app","path":"/home/private"}])
        self.assertNotIn("sensitive_private_app",str(a))
        self.assertFalse(a["actual_wsgi_sha256_verified"])
    def test_18_unreadable_list_fails_closed(self):
        with self.assertRaises(ValueError):
            u._lead_summary(None)
    def test_19_encrypted_without_marker_counts(self):
        name="20261114-ABCDEF0123456789AB.json"
        a=u._lead_summary([{"file":name,"type":"file"}])
        self.assertEqual(a["candidate_records_without_dispatch_marker"],1)
        self.assertNotIn(name,str(a))
    def test_20_marker_only_counts_queued_not_delivered(self):
        name="20261114-ABCDEF0123456789AB.json"
        marker=".owner-dispatched-"+hashlib.sha256(name.encode("ascii")).hexdigest()+".json"
        a=u._lead_summary([{"file":name,"type":"file"},{"file":marker,"type":"file"}])
        self.assertEqual(a["marker_filenames_matched"],1)
        self.assertFalse(a["dispatch_marker_is_proof_of_delivered_email"])
    def test_21_link_type_does_not_count(self):
        a=u._lead_summary([{"file":"20261114-ABCDEF0123456789AB.json","type":"link"}])
        self.assertEqual(a["encrypted_record_filename_candidates"],0)
    def test_22_duplicate_record_denied(self):
        n="20261114-ABCDEF0123456789AB.json"
        with self.assertRaises(ValueError):
            u._lead_summary([{"file":n,"type":"file"},{"file":n,"type":"file"}])
    def test_23_too_many_rows_denied(self):
        with self.assertRaises(ValueError):
            u._list_of_records([{}]*u.MAX_ROWS)
    def test_24_transport_not_merchants_statement(self):
        r=u.run("")
        self.assertFalse(r["merchant_balance_verified"])
        self.assertFalse(r["payment_processed"])
        self.assertFalse(r["messages_sent"])
    def test_25_unknown_handler_response_not_authorized(self):
        with patch.object(u,"_request",side_effect=ValueError("denied")):
            result=u.run(TOKEN)
        self.assertEqual(result["status"],"no_verified_api_result")
        self.assertTrue(all(item["status"]=="held" for item in result["checks"].values()))
    def test_26_valid_mocked_listings_never_decrypt(self):
        with patch.object(u,"_request",side_effect=[[],[{"email":"support@mojplaywin.com"}],[]]):
            result=u.run(TOKEN)
        self.assertEqual(result["status"],"partial_verified_uapi")
        self.assertFalse(result["lead_payload_read"])
        self.assertTrue(result["checks"]["support"]["support_mailbox_configured"])
    def test_27_no_mail_send_api_function(self):
        for name,func in (("Email","send_mail"),("Email","add_pop"),("Fileman","save_file_content")):
            with self.assertRaises(ValueError):
                u._request(name,func,{},TOKEN,opener=FakeOpener(good([])))
    def test_28_http_status_error_never_logs_payload(self):
        with patch.object(u,"_request",side_effect=HTTPError("url",403,"forbidden",{},None)):
            result=u.run(TOKEN)
        self.assertEqual(result["checks"]["support"]["http_status"],403)
        self.assertNotIn("url",str(result))
    def test_29_network_error_captured_without_key(self):
        with patch.object(u,"_request",side_effect=URLError("timeout")):
            result=u.run(TOKEN)
        self.assertNotIn(TOKEN,str(result))
    def test_30_token_metadata_not_exported(self):
        with patch.object(u,"_request",side_effect=[[],[],[]]):
            result=u.run(TOKEN)
        self.assertNotIn(TOKEN,json.dumps(result))

if __name__=="__main__":
    unittest.main()

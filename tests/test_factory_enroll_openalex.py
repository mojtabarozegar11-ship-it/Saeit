"""Unit tests for private OpenAlex owner-approved enrollment. No outside requests."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest import mock

PATH=Path(__file__).resolve().parents[1]/"scripts/factory_enroll_openalex.py"
spec=importlib.util.spec_from_file_location("factory_enroll_openalex",PATH)
ENROLL=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ENROLL)

class Response:
    status=201
    def __init__(self,packet):
        self.raw=json.dumps(packet).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.raw[:size]

class EnrollmentTests(unittest.TestCase):
    email="mojtaba.rozegar11@gmail.com"
    token="oax_dummy_key_private_987654321"
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target=Path(self.tmp.name)/".openalex-api-key"

    def test_pending_key_private_atomic_and_no_reregister(self):
        seen=[]
        def fetch(req,timeout):
            seen.append((req.full_url, req.get_method(), timeout,
                         json.loads(req.data)))
            return Response({"api_key":self.token,"status":"pending_activation",
                             "email":self.email})
        answer=ENROLL.enroll(self.email,self.target,fetch=fetch)
        self.assertEqual(answer,"EMAIL_ACTIVATION_REQUIRED")
        self.assertEqual(self.target.read_text(),self.token+"\n")
        self.assertEqual(self.target.stat().st_mode & 0o777,0o600)
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0][0],"https://api.openalex.org/api-keys")
        self.assertEqual(seen[0][1],"POST")
        self.assertEqual(seen[0][3]["email"],self.email)
        self.assertEqual(ENROLL.enroll(self.email,self.target,fetch=lambda *a,**k:
                                       self.fail("never register twice")),
                         "ALREADY_CONFIGURED")

    def test_registration_conflict_never_creates_key(self):
        data=json.dumps({"error":"activation_pending"}).encode()
        def fetch(*args,**kwargs):
            raise urllib.error.HTTPError(ENROLL.URL,409,"conflict",{},
                                         io.BytesIO(data))
        self.assertEqual(ENROLL.enroll(self.email,self.target,fetch=fetch),
                         "ACTIVATION_ALREADY_PENDING")
        self.assertFalse(self.target.exists())

    def test_bad_key_or_account_cannot_be_persisted(self):
        response={"api_key":"short","status":"pending_activation",
                  "email":self.email}
        answer=ENROLL.enroll(self.email,self.target,fetch=lambda *a,**k:
                              Response(response))
        self.assertEqual(answer,"PROVIDER_UNEXPECTED_KEY_RESPONSE")
        self.assertFalse(self.target.exists())
        response["api_key"]=self.token
        response["email"]="someone@example.org"
        self.assertEqual(ENROLL.enroll(self.email,self.target,fetch=lambda *a,**k:
                                        Response(response)),
                         "PROVIDER_UNEXPECTED_KEY_RESPONSE")
        self.assertFalse(self.target.exists())

    def test_symlinks_and_insecure_existing_credentials_refused(self):
        other=Path(self.tmp.name)/"other"
        other.write_text("unsafe")
        self.target.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,"OPENALEX_CREDENTIAL_SYMLINK"):
            ENROLL.enroll(self.email,self.target)
        self.target.unlink()
        self.target.write_text("secret")
        os.chmod(self.target,0o644)
        with self.assertRaisesRegex(RuntimeError,"OPENALEX_EXISTING_CREDENTIAL_UNSAFE"):
            ENROLL.enroll(self.email,self.target)

    def test_server_errors_do_not_expose_untrusted_response(self):
        def fetch(*args,**kwargs):
            raise urllib.error.HTTPError(ENROLL.URL,500,
                                         "MY_SECRET_VALUE",{},
                                         io.BytesIO(b"MY_SECRET_VALUE"))
        self.assertEqual(ENROLL.enroll(self.email,self.target,fetch=fetch),
                         "PROVIDER_HTTP_ERROR_500")
        self.assertFalse(self.target.exists())

if __name__ == "__main__": unittest.main()

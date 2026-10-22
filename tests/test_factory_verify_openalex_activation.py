"""No-network proofs for safe Stage 2 OpenAlex activation and queue resumption."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error

SOURCE=Path(__file__).resolve().parents[1]/"scripts/factory_verify_openalex_activation.py"
spec=importlib.util.spec_from_file_location("factory_verify_openalex",SOURCE)
VERIFY=importlib.util.module_from_spec(spec)
spec.loader.exec_module(VERIFY)

class Response:
    status=200
    def __init__(self,payload):
        self.payload=json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.payload[:size]

class ActivationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.stage=self.root/"production-instructions"/"stage-02"
        self.stage.mkdir(parents=True)
        self.operations=self.root/"operations"
        self.operations.mkdir()
        self.key=self.operations/".openalex-api-key"
        self.key.write_text("TestPrivateKey_123456789123456789\n")
        os.chmod(self.key,0o600)

    def test_authenticated_get_not_key_in_results(self):
        seen=[]
        def fetch(req,timeout):
            seen.append((req.get_header("Authorization"),req.full_url,timeout))
            return Response({"results":[]})
        token=VERIFY.private_key(self.operations)
        self.assertEqual(VERIFY.authenticated_probe(token,fetch=fetch),"ACTIVE")
        self.assertEqual(seen,[("Bearer "+token,VERIFY.API,25)])

    def test_unactivated_key_preserves_factory(self):
        def fetch(req,timeout):
            raise urllib.error.HTTPError(VERIFY.API,403,"not verified",{},
                                         io.BytesIO(b"private error details"))
        self.assertEqual(VERIFY.authenticated_probe("PrivateToken_XYZ123456789",
                                                   fetch=fetch),
                         "PENDING_OR_UNAUTHORIZED")
        self.assertFalse((self.stage/"literature-provider-cooldowns.json").exists())

    def test_verified_credential_releases_only_openalex_quota(self):
        path=self.stage/"literature-provider-cooldowns.json"
        saved={"schema":VERIFY.SCHEMA,
               "openalex_credential_mode":"keyed",
               "blocked_until_utc":{VERIFY.ENDPOINT:"2099-01-01T00:00:00+00:00",
                                    "https://api.crossref.org/works":"2099-01-01T00:00:00+00:00"},
               "checked_utc":"2026-10-22T18:00:00+00:00"}
        path.write_text(json.dumps(saved))
        os.chmod(path,0o600)
        self.assertEqual(VERIFY.release_verified_cooldown(self.root),"RELEASED")
        packet=json.loads(path.read_text())
        self.assertNotIn(VERIFY.ENDPOINT,packet["blocked_until_utc"])
        self.assertIn("https://api.crossref.org/works",packet["blocked_until_utc"])
        self.assertEqual(VERIFY.release_verified_cooldown(self.root),"NOT_BLOCKED")

    def test_symlink_or_loose_key_never_used(self):
        os.chmod(self.key,0o644)
        with self.assertRaisesRegex(RuntimeError,"PERMISSIONS"):
            VERIFY.private_key(self.operations)
        self.key.unlink()
        other=self.operations/"unsafe"
        other.write_text("leaked")
        self.key.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,"ABSENT_OR_UNSAFE"):
            VERIFY.private_key(self.operations)

    def test_not_keyed_cooldown_is_never_released(self):
        path=self.stage/"literature-provider-cooldowns.json"
        path.write_text(json.dumps({
            "schema":VERIFY.SCHEMA,"openalex_credential_mode":"anonymous",
            "blocked_until_utc":{VERIFY.ENDPOINT:"2099-01-01T00:00:00+00:00"}
        }))
        os.chmod(path,0o600)
        self.assertEqual(VERIFY.release_verified_cooldown(self.root),"AUTH_MODE_CHANGED")
        self.assertIn(VERIFY.ENDPOINT,json.loads(path.read_text())["blocked_until_utc"])

if __name__=="__main__":
    unittest.main()

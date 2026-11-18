import io
import unittest
from unittest.mock import Mock
from urllib.error import URLError, HTTPError
from scripts.zomorod_b2b_public_observation_20261118 import (
    classify, observe, ROUTES, NoRedirect, LIMIT, ORIGIN,
)

class PublicObservationTests(unittest.TestCase):
    def test_200_not_proof_of_release(self):
        self.assertEqual(classify(200,b"x"),"HTTP_200_ONLY")
        self.assertEqual(classify(200,b"x",b"y"),"HTTP_200_DIFFERENT_BYTES")

    def test_exact_reviewed_bytes(self):
        self.assertEqual(classify(200,b"x",b"x"),"EXACT_REVIEWED_BYTES")
        self.assertEqual(classify(404,b"x",b"x"),"NOT_HTTP_200")

    def test_fixed_scope_and_get_only(self):
        opener=Mock()
        with self.assertRaises(ValueError):
            observe("/private/",opener)
        opener.open.assert_not_called()
        self.assertEqual(len(ROUTES),6)

    def test_transport_failure_is_unknown_status(self):
        opener=Mock()
        opener.open.side_effect=URLError("unreachable")
        result=observe("/",opener)
        self.assertIsNone(result["status"])
        self.assertFalse(result["tls_verified"])
        self.assertEqual(result["classification"],"TRANSPORT_OR_LOCAL_ERROR")
        request=opener.open.call_args.args[0]
        self.assertEqual(request.get_method(),"GET")
        self.assertEqual(request.full_url,ORIGIN+"/")

    def test_redirect_is_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,"",{},"https://example.com/"))
        opener=Mock()
        opener.open.side_effect=HTTPError(ORIGIN+"/",302,"",{},io.BytesIO(b""))
        result=observe("/",opener)
        self.assertEqual(result["status"],302)
        self.assertEqual(result["classification"],"HTTP_ERROR_OR_REDIRECT")

    def test_oversized_response_not_accepted(self):
        opener=Mock()
        response=opener.open.return_value.__enter__.return_value
        response.status=200
        response.geturl.return_value=ORIGIN+"/"
        response.read.return_value=b"x"*(LIMIT+1)
        self.assertEqual(observe("/",opener)["classification"],"BODY_TOO_LARGE")

    def test_non_html_response_not_accepted(self):
        opener=Mock()
        response=opener.open.return_value.__enter__.return_value
        response.status=200
        response.geturl.return_value=ORIGIN+"/"
        response.read.return_value=b"{}"
        response.headers.get_content_type.return_value="application/json"
        self.assertEqual(observe("/",opener)["classification"],"NON_HTML_RESPONSE")

if __name__=="__main__":
    unittest.main()

"""Executable integrity tests for owner-gated *read-only* MojPlayWin GET cutover.

No network, customer records, invoice issuance or chain transactions.
"""
import io
import unittest
from email.message import Message

from services.mpw_checkout_release_assurance import (
    MAX_ROUTE_BODY_BYTES as LIMIT,
    read_bounded_response,
    checkout_release_get_category,
    BODY_OVERSIZE, BODY_NOT_PROVEN, LENGTH_INVALID, LENGTH_MISMATCH,
    HEADER_AMBIGUOUS, CSP_MISSING, CSP_SCRIPT,
    CHECKOUT_BODY_OK,
)

CSP = ("default-src 'self'; script-src 'none'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'self'")
EMAIL = '<input type="email" name="email" required maxlength="254" autocomplete="email">'
CSRF = '<input type="hidden" name="csrfmiddlewaretoken" value="' + 'A'*64 + '">'
FORM = '<form method="post" action="/commerce/trx-easy/start/72/">'
BUTTON = '<button type="submit">Create TRX payment invoice</button>'


def html():
    return ('<!doctype html><html><head><title>Checkout</title></head><body><main>' +
            FORM + CSRF + EMAIL + BUTTON + '</form></main></body></html>').encode("utf-8")


def headers(**overrides):
    o=Message()
    for name,value in [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Security-Policy", CSP),
        ("Cache-Control", "private, no-store"),
    ]:
        o[name] = overrides.get(name, value)
    for name,value in overrides.items():
        if name not in ("Content-Type", "Content-Security-Policy", "Cache-Control"):
            o[name]=value
    return o


class Reply:
    def __init__(self, payload=b"ok", hdrs=None, error=None):
        self.payload = payload
        self.headers = headers() if hdrs is None else hdrs
        self.error = error
        self.last_limit = None
        self.reads = 0

    def read(self, bound):
        self.last_limit = bound
        self.reads += 1
        if self.error is not None:
            raise self.error
        if type(self.payload) is not bytes:
            return self.payload
        return self.payload[:bound]


class ContentIntegrityTests(unittest.TestCase):
    def classify(self, h=None, data=None):
        return checkout_release_get_category(html() if data is None else data,
                                             headers() if h is None else h,72)

    def test_01_two_byte_regular_response_reads(self):
        self.assertEqual(read_bounded_response(Reply(b"ok")),(b"ok",None))

    def test_02_limit_plus_one_probe_executed(self):
        r=Reply(b"ok")
        read_bounded_response(r)
        self.assertEqual(r.last_limit, LIMIT+1)
        self.assertEqual(r.reads, 1)

    def test_03_exact_boundary_is_allowed(self):
        raw=b"A"*LIMIT
        self.assertEqual(read_bounded_response(Reply(raw)), (raw,None))

    def test_04_one_byte_over_limit_rejected(self):
        self.assertEqual(read_bounded_response(Reply(b"A"*(LIMIT+1)))[1], BODY_OVERSIZE)

    def test_05_multi_megabyte_payload_reads_only_cap_plus_one(self):
        r=Reply(b"Z"*(LIMIT*6))
        self.assertEqual(read_bounded_response(r)[1],BODY_OVERSIZE)
        self.assertEqual(r.last_limit,LIMIT+1)

    def test_06_empty_body_is_bounded_but_not_checkout(self):
        self.assertEqual(read_bounded_response(Reply(b"")),(b"",None))
        self.assertNotEqual(self.classify(data=b""),CHECKOUT_BODY_OK)

    def test_07_wrong_type_str_refused(self):
        self.assertEqual(read_bounded_response(Reply("a"))[1],BODY_NOT_PROVEN)

    def test_08_wrong_type_bytearray_refused(self):
        self.assertEqual(read_bounded_response(Reply(bytearray(b"a")))[1],BODY_NOT_PROVEN)

    def test_09_oserror_read_refused(self):
        self.assertEqual(read_bounded_response(Reply(error=OSError("private details")))[1],BODY_NOT_PROVEN)

    def test_10_valueerror_read_refused(self):
        self.assertEqual(read_bounded_response(Reply(error=ValueError("invalid stream")))[1],BODY_NOT_PROVEN)

    def test_11_content_length_matches(self):
        r=Reply(b"abc",headers(**{"Content-Length":"3"}))
        self.assertEqual(read_bounded_response(r),(b"abc",None))

    def test_12_content_length_larger_than_returned_body_is_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"4"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_MISMATCH)

    def test_13_content_length_smaller_than_returned_body_is_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"2"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_MISMATCH)

    def test_14_oversized_declared_length_prevents_read(self):
        r=Reply(b"abc",headers(**{"Content-Length":str(LIMIT+1)}))
        self.assertEqual(read_bounded_response(r)[1], BODY_OVERSIZE)
        self.assertEqual(r.reads,0)

    def test_15_bad_negative_content_length_is_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"-1"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_INVALID)

    def test_16_bad_scientific_content_length_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"3e0"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_INVALID)

    def test_17_bad_float_content_length_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"3.0"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_INVALID)

    def test_18_bad_surrounding_space_length_rejected(self):
        r=Reply(b"abc",headers(**{"Content-Length":"3 4"}))
        self.assertEqual(read_bounded_response(r)[1], LENGTH_INVALID)

    def test_19_duplicate_content_length_rejected(self):
        h=headers(**{"Content-Length":"3"})
        h["Content-Length"]="3"
        self.assertEqual(read_bounded_response(Reply(b"abc",h))[1], HEADER_AMBIGUOUS)

    def test_20_conflicting_content_length_rejected(self):
        h=headers(**{"Content-Length":"3"})
        h["Content-Length"]="999"
        self.assertEqual(read_bounded_response(Reply(b"abc",h))[1], HEADER_AMBIGUOUS)

    def test_21_duplicate_csp_refused_before_body_read(self):
        h=headers()
        h["Content-Security-Policy"]="script-src 'unsafe-inline'"
        r=Reply(b"abc",h)
        self.assertEqual(read_bounded_response(r)[1],HEADER_AMBIGUOUS)
        self.assertEqual(r.reads,0)

    def test_22_duplicate_content_type_refused(self):
        h=headers()
        h["Content-Type"]="application/json"
        self.assertEqual(read_bounded_response(Reply(b"a",h))[1],HEADER_AMBIGUOUS)

    def test_23_duplicate_cache_control_refused(self):
        h=headers()
        h["Cache-Control"]="public"
        self.assertEqual(read_bounded_response(Reply(b"a",h))[1],HEADER_AMBIGUOUS)

    def test_24_duplicate_transfer_encoding_refused(self):
        h=headers(**{"Transfer-Encoding":"chunked"})
        h["Transfer-Encoding"]="gzip"
        self.assertEqual(read_bounded_response(Reply(b"a",h))[1],HEADER_AMBIGUOUS)

    def test_25_csp_duplicate_in_markup_classifier_rejected(self):
        h=headers()
        h["Content-Security-Policy"]="script-src 'unsafe-inline'"
        self.assertEqual(self.classify(h),HEADER_AMBIGUOUS)

    def test_26_content_type_duplicate_in_markup_classifier_rejected(self):
        h=headers()
        h["Content-Type"]="application/xhtml+xml"
        self.assertEqual(self.classify(h),HEADER_AMBIGUOUS)

    def test_27_cache_control_duplicate_in_markup_classifier_rejected(self):
        h=headers()
        h["Cache-Control"]="public"
        self.assertEqual(self.classify(h),HEADER_AMBIGUOUS)

    def test_28_missing_csp_still_denied(self):
        h=headers()
        del h["Content-Security-Policy"]
        self.assertEqual(self.classify(h),CSP_MISSING)

    def test_29_unsafe_script_csp_still_denied(self):
        h=headers(**{"Content-Security-Policy":CSP.replace("script-src 'none'","script-src 'unsafe-inline'")})
        self.assertEqual(self.classify(h),CSP_SCRIPT)

    def test_30_complete_html_with_single_headers_still_passes_get_only(self):
        self.assertEqual(self.classify(),CHECKOUT_BODY_OK)

    def test_31_max_bytes_bool_invalid(self):
        self.assertEqual(read_bounded_response(Reply(b"a"),max_bytes=True)[1],LENGTH_INVALID)

    def test_32_max_bytes_zero_invalid(self):
        self.assertEqual(read_bounded_response(Reply(b"a"),max_bytes=0)[1],LENGTH_INVALID)

    def test_33_max_bytes_above_cap_invalid(self):
        self.assertEqual(read_bounded_response(Reply(b"a"),max_bytes=LIMIT+1)[1],LENGTH_INVALID)

    def test_34_max_bytes_one_accepts_one_byte(self):
        self.assertEqual(read_bounded_response(Reply(b"a"),max_bytes=1),(b"a",None))

    def test_35_explicit_length_zero_with_empty_bytes_allowed_for_generic_get(self):
        self.assertEqual(read_bounded_response(Reply(b"",headers(**{"Content-Length":"0"}))),(b"",None))

    def test_36_invalid_length_does_not_print_or_return_header_contents(self):
        r=Reply(b"safe",headers(**{"Content-Length":"SECRET_HEADER_CONTENT"}))
        data,cat=read_bounded_response(r)
        self.assertIsNone(data)
        self.assertEqual(cat,LENGTH_INVALID)
        self.assertNotIn("SECRET_",cat)

    def test_37_carriage_return_security_header_denied(self):
        class Header:
            def get(self,k): return CSP+"\r\nscript-src 'unsafe-inline'" if k=="Content-Security-Policy" else {
                "Content-Type":"text/html","Cache-Control":"no-store"}.get(k)
        self.assertNotEqual(self.classify(Header()),CHECKOUT_BODY_OK)

    def test_38_overlong_csp_denied(self):
        h=headers(**{"Content-Security-Policy":"script-src "+("x"*4500)})
        self.assertEqual(self.classify(h),CSP_MISSING)

    def test_39_content_length_of_limited_page_must_equal_read_bytes(self):
        r=Reply(b"hello",headers(**{"Content-Length":"4"}))
        self.assertEqual(read_bounded_response(r)[1],LENGTH_MISMATCH)

    def test_40_body_header_proof_does_not_imply_paid_status(self):
        self.assertIn("not_paid",self.classify())

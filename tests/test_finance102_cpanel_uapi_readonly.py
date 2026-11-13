"""Mock-only cPanel UAPI verification: no real token, HTTP request or server write."""
import json
import unittest

from scripts.finance102_cpanel_uapi_readonly import (
    API_URL, classify, parse_uapi_response, run,
)


def fixture():
    return {
        "status": 1, "errors": None, "messages": None, "metadata": {}, "warnings": None,
        "data": [
            {"domain": "zomorodmelal.ir", "base_uri": "/", "path": "/home/zomorod2/Saeit"},
            {"domain": "mojplaywin.com", "base_uri": "/", "path": "/home/zomorod2/Saeit-staging"},
        ],
    }


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return json.dumps(self.data).encode("utf8")[:limit]


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.req = None

    def open(self, request, timeout):
        self.req = request
        assert timeout == 15
        return FakeResponse(self.data)


class Tests(unittest.TestCase):
    def test_get_only_readonly_api(self):
        self.assertEqual(
            API_URL, "https://zohal.pws-dns.net:2083/execute/PassengerApps/list_applications"
        )
        self.assertNotIn("upload", API_URL)

    def test_direct_execute_envelope_with_warnings(self):
        opener = FakeOpener(fixture())
        self.assertEqual(run("T" * 20, opener), {
            "zomorodmelal.ir": True, "mojplaywin.com": True,
        })
        self.assertEqual(opener.req.get_method(), "GET")
        self.assertEqual(opener.req.full_url, API_URL)
        self.assertTrue(
            opener.req.get_header("Authorization").startswith("cpanel zomorod2:")
        )

    def test_identity_verified_api_v3_wrapper(self):
        wrapped = {
            "apiversion": 3, "module": "PassengerApps",
            "func": "list_applications", "result": fixture(),
        }
        self.assertTrue(all(parse_uapi_response(wrapped).values()))
        self.assertTrue(all(run("T" * 20, FakeOpener(wrapped)).values()))

    def test_legacy_bare_result_cannot_assert_authentication(self):
        with self.assertRaises(ValueError):
            parse_uapi_response({"result": fixture()})
        for field, wrong in (
            ("apiversion", 2), ("module", "Fileman"), ("func", "delete_file"),
        ):
            envelope = {
                "apiversion": 3, "module": "PassengerApps",
                "func": "list_applications", "result": fixture(),
            }
            envelope[field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_uapi_response(envelope)

    def test_missing_token_mismatch_and_duplicate_records(self):
        with self.assertRaises(ValueError):
            run(None, FakeOpener(fixture()))
        with self.assertRaises(ValueError):
            run("bad\ncredential", FakeOpener(fixture()))
        empty = fixture()
        empty["data"] = []
        self.assertFalse(all(classify(empty).values()))
        duplicates = fixture()
        duplicates["data"].append(duplicates["data"][0])
        self.assertFalse(classify(duplicates)["zomorodmelal.ir"])

    def test_fail_closed_on_corruption_and_bad_status(self):
        for status in (0, False, None):
            corrupted = fixture()
            corrupted["status"] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                classify(corrupted)
        with self.assertRaises(ValueError):
            classify({"status": 1})
        corrupted = fixture()
        corrupted["data"] = None
        with self.assertRaises(ValueError):
            classify(corrupted)
        with self.assertRaises(ValueError):
            parse_uapi_response({"error": "not authorized"})

    def test_missing_application_is_not_success(self):
        result = fixture()
        result["data"] = result["data"][:1]
        self.assertEqual(classify(result), {
            "zomorodmelal.ir": True, "mojplaywin.com": False,
        })


if __name__ == "__main__":
    unittest.main()

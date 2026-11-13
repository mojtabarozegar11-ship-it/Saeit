"""Mock-only TLS preflight tests; no network, token, login or host writes."""
import unittest
from scripts.finance102_cpanel_tls_preflight import check, HOST, EXPECTED_IPV4, PORT


def lookup(addr):
    return [(2, 1, 6, "", (addr, PORT))]


class MockSock:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def version(self): return "TLSv1.3"


class MockContext:
    def __init__(self): self.hostname = None
    def wrap_socket(self, sock, server_hostname):
        self.hostname = server_hostname
        return MockSock()


class Tests(unittest.TestCase):
    def test_expected_target_exact(self):
        self.assertEqual((HOST, EXPECTED_IPV4, PORT),
                         ("zohal.pws-dns.net", "178.239.147.125", 2083))

    def test_dns_drift_fails_closed_before_tcp(self):
        calls = []
        def fail_dial(*args, **kwargs):
            calls.append(True)
            raise AssertionError("must not dial")
        state = check(lambda *a: lookup("178.239.147.124"), fail_dial, MockContext())
        self.assertFalse(state["dns_exact_expected_ipv4"])
        self.assertFalse(state["tls_hostname_and_ca_verified"])
        self.assertEqual(calls, [])

    def test_valid_tls_proves_no_authentication(self):
        ctxt = MockContext()
        connections = []
        def fake_dial(target, timeout):
            connections.append((target, timeout))
            return MockSock()
        state = check(lambda *a: lookup(EXPECTED_IPV4), fake_dial, ctxt)
        self.assertEqual(connections, [((EXPECTED_IPV4, PORT), 8)])
        self.assertEqual(ctxt.hostname, HOST)
        self.assertTrue(state["tls_hostname_and_ca_verified"])
        self.assertFalse(state["authenticated"])
        self.assertFalse(state["filesystem_inspected"])
        self.assertFalse(state["deployment_performed"])

    def test_tls_failure_fails_closed(self):
        class FailContext:
            def wrap_socket(self, sock, server_hostname): raise OSError("TLS failed")
        state = check(lambda *a: lookup(EXPECTED_IPV4),
                      lambda *a, **k: MockSock(), FailContext())
        self.assertTrue(state["dns_exact_expected_ipv4"])
        self.assertFalse(state["tls_hostname_and_ca_verified"])

if __name__ == "__main__":
    unittest.main()

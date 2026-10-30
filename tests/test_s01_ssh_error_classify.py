"""S-01 offline SSH classification tests: no network, no secrets, no host mutation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from s01_ssh_error_classify import classify

class ClassifierTests(unittest.TestCase):
    def test_auth(self): self.assertEqual(classify("Permission denied (publickey)."), "AUTH_REJECTED")
    def test_host_key(self): self.assertEqual(classify("Host key verification failed."), "HOST_KEY_REJECTED")
    def test_network(self): self.assertEqual(classify("connect to host: Connection timed out"), "TRANSPORT_UNREACHABLE")
    def test_banner(self): self.assertEqual(classify("kex_exchange_identification: read: Connection reset"), "BANNER_OR_KEX_FAILED")
    def test_dns(self): self.assertEqual(classify("Could not resolve hostname relay"), "DNS_RESOLUTION_FAILED")
    def test_secret_never_returned(self): self.assertEqual(classify("token=private-example /home/owner/secret"), "UNKNOWN_SAFE_FAILURE")
    def test_empty(self): self.assertEqual(classify(""), "EMPTY_STDERR")
    def test_blank(self): self.assertEqual(classify("  \n"), "EMPTY_STDERR")
    def test_proxy_channel(self): self.assertEqual(classify("channel 0: open failed: administratively prohibited"), "PROXY_CHANNEL_REJECTED")
    def test_proxy_closed(self): self.assertEqual(classify("Connection closed by UNKNOWN port 65535"), "TRANSPORT_RESET_OR_CLOSED")
    def test_reset(self): self.assertEqual(classify("read: Connection reset by peer"), "TRANSPORT_RESET_OR_CLOSED")
    def test_mux(self): self.assertEqual(classify("mux_client_request_session: read from master failed"), "CONTROL_SOCKET_FAILURE")
    def test_remote_identity(self): self.assertEqual(classify("debug1: Sending command: test\ndebug1: Exit status 1"), "REMOTE_IDENTITY_CHECK_REJECTED")
    def test_debug_success(self): self.assertEqual(classify("debug1: Authenticated to example\ndebug1: Exit status 0"), "REMOTE_COMMAND_SUCCEEDED")
    def test_secret_with_known_failure(self): self.assertEqual(classify("private-key-material Permission denied"), "AUTH_REJECTED")

if __name__ == "__main__":
    unittest.main()

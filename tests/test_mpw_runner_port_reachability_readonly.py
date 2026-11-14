"""No-network behavioral tests of bounded GitHub-runner TCP diagnostics."""
import socket
import unittest
from unittest.mock import patch
from scripts import mpw_runner_port_reachability_readonly as n

class PortProbeTests(unittest.TestCase):
    def test_01_whitelist_five(self):
        self.assertEqual(len(n.TARGETS),5)
    def test_02_target_ports(self):
        self.assertEqual([p for _,_,p in n.TARGETS],[22,1396,443,443,443])
    def test_03_bound_timeout(self):
        self.assertLessEqual(n.TIMEOUT_SECONDS,3)
    def test_04_tcp_success_no_false_auth(self):
        class Conn:
            def __enter__(self):return self
            def __exit__(self,*args):return None
        with patch.object(n.socket,"create_connection",return_value=Conn()):
            result=n.probe("test","host",443)
        self.assertEqual(result["status"],"tcp_connected")
        self.assertFalse(result["ssh_authenticated"])
    def test_05_dns_failed(self):
        with patch.object(n.socket,"create_connection",side_effect=socket.gaierror()):
            result=n.probe("test","bad",443)
        self.assertEqual(result["status"],"dns_failed")
    def test_06_tcp_timeout(self):
        with patch.object(n.socket,"create_connection",side_effect=socket.timeout()):
            result=n.probe("test","host",443)
        self.assertEqual(result["status"],"tcp_timeout")
    def test_07_tcp_refused(self):
        with patch.object(n.socket,"create_connection",side_effect=ConnectionRefusedError()):
            result=n.probe("test","host",443)
        self.assertEqual(result["status"],"tcp_refused")
    def test_08_generic_socket_error(self):
        with patch.object(n.socket,"create_connection",side_effect=OSError()):
            result=n.probe("test","host",443)
        self.assertEqual(result["status"],"tcp_network_or_socket_error")
    def test_09_no_payload_or_credentials(self):
        with patch.object(n.socket,"create_connection",side_effect=socket.timeout()) as call:
            result=n.run((("x","host",443),))
        self.assertEqual(call.call_count,1)
        self.assertFalse(result["files_modified"])
        self.assertFalse(result["messages_sent"])
        self.assertFalse(result["money_spent"])
    def test_10_limit_refuses_extra_host(self):
        with self.assertRaises(ValueError):
            n.run(tuple(("h","example.org",80) for _ in range(6)))
    def test_11_run_is_not_authenticated(self):
        with patch.object(n.socket,"create_connection",side_effect=socket.timeout()):
            result=n.run()
        self.assertTrue(all(x["account_verified"] is False for x in result["tests"]))
        self.assertTrue(all(x["payment_confirmed"] is False for x in result["tests"]))
    def test_12_elapsed_nonnegative(self):
        with patch.object(n.socket,"create_connection",side_effect=socket.timeout()):
            self.assertGreaterEqual(n.probe("a","b",3)["probe_ms"],0)

if __name__=="__main__":
    unittest.main()

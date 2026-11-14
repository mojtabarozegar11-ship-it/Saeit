"""No real socket connections occur in these offline tests."""
import unittest
from scripts.finance102_network_preflight import TARGETS, snapshot

class Finance102NetworkPreflightTest(unittest.TestCase):
    def test_only_exact_allowlisted_owner_hosts(self):
        self.assertEqual(TARGETS, (
            ("factory_vps_ssh","178.239.147.150",22),
            ("cpanel_private_ssh","178.239.147.125",1396),
            ("cpanel_https","178.239.147.125",2083),
            ("cpanel_https_standard","178.239.147.125",443),
        ))
    def test_timeout_and_unavailable_do_not_claim_release(self):
        called=[]
        def failed(hostport,timeout):
            called.append((hostport,timeout))
            raise TimeoutError()
        data=snapshot(failed)
        self.assertEqual(len(called),4)
        self.assertTrue(all(t==5 for _,t in called))
        self.assertEqual(set(data["results"].values()),{"TCP_UNREACHABLE_FROM_RUNNER"})
        self.assertFalse(data["authentication_proven"])
        self.assertFalse(data["hosting_file_parity_proven"])
        self.assertFalse(data["deployment_authorized"])
        self.assertFalse(data["deployment_performed"])
    def test_socket_connect_success_not_authentication(self):
        class Dummy:
            def __enter__(self): return self
            def __exit__(self,*a): return False
        data=snapshot(lambda addr,timeout: Dummy())
        self.assertEqual(set(data["results"].values()),{"TCP_CONNECTED"})
        self.assertFalse(data["authentication_proven"])
        self.assertFalse(data["deployment_performed"])

if __name__=="__main__": unittest.main()

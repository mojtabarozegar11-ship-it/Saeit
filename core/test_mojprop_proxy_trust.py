"""Public request rate limits must not accept attacker-chosen proxy headers."""
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.mojprop_views import _client_ip, _ip_hash


class MojPropProxyBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_untrusted_real_ip_header_cannot_change_rate_identity(self):
        first = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="203.0.113.18",
                                  HTTP_X_REAL_IP="198.51.100.40")
        second = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="203.0.113.18",
                                   HTTP_X_REAL_IP="198.51.100.41")
        self.assertEqual(_client_ip(first), "203.0.113.18")
        self.assertEqual(_ip_hash(first), _ip_hash(second))

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=("10.10.10.5",))
    def test_explicit_trusted_proxy_may_relay_valid_client_address(self):
        req = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="10.10.10.5",
                                HTTP_X_REAL_IP="2001:db8::1")
        self.assertEqual(_client_ip(req), "2001:db8::1")

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=("10.10.10.5",))
    def test_invalid_claimed_ip_does_not_bypass_rate_bucket(self):
        req = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="10.10.10.5",
                                HTTP_X_REAL_IP="1.2.3.4, 5.6.7.8")
        self.assertEqual(_client_ip(req), "10.10.10.5")

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=("10.10.10.5",))
    def test_unlisted_proxy_cannot_relay_claimed_address(self):
        req = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="10.10.10.6",
                                HTTP_X_REAL_IP="192.0.2.42")
        self.assertEqual(_client_ip(req), "10.10.10.6")

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS="*")
    def test_wildcard_proxy_text_is_not_an_authorized_peer_list(self):
        req = self.factory.post("/moj-prop-intake/", REMOTE_ADDR="198.51.100.19",
                                HTTP_X_REAL_IP="192.0.2.42")
        self.assertEqual(_client_ip(req), "198.51.100.19")

    def test_missing_remote_addr_uses_shared_unknown_bucket_not_attacker_value(self):
        req = self.factory.post("/moj-prop-intake/", HTTP_X_REAL_IP="203.0.113.1")
        req.META.pop("REMOTE_ADDR", None)
        self.assertEqual(_client_ip(req), "unknown")

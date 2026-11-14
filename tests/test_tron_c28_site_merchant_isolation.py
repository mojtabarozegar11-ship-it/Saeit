"""Per-site TRX merchant legal identity and wallet separation, no live transfers."""
import hashlib
from dataclasses import replace
from django.test import SimpleTestCase
from core.tron_gateway_verify import ALPHABET, MAINNET_RECEIVER, address_hex
from core.tron_gateway_merchant_registry import (
    SiteMerchant, MerchantConfigurationError, configured_site_merchant,
)

def synthetic_public_mainnet_address():
    # Deliberately synthetic public-only test receiver, NOT an owned wallet.
    raw=bytes([0x41])+bytes([0x05])*20
    checksum=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    n=int.from_bytes(raw+checksum,"big")
    chars=[]
    while n:
        n,rem=divmod(n,58)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))

SECOND = synthetic_public_mainnet_address()
FIRST = MAINNET_RECEIVER


def row(tenant, receiver, *, approved=True, network="tron-mainnet", asset="TRX"):
    return {"tenant_id":tenant, "receiver":receiver, "approved":approved,
            "network":network, "asset":asset}

class ReceiverAndTenantSeparationTests(SimpleTestCase):
    def setUp(self):
        self.registry={
            "mojplaywin.com":row("mojplaywin_site",FIRST),
            "zomorodmelal.ir":row("zomorodmelal_site",SECOND),
        }

    def lookup(self, host="mojplaywin.com", registry=None):
        return configured_site_merchant(
            host, self.registry if registry is None else registry)

    def test_01_first_site_exact_tenant_and_wallet(self):
        m=self.lookup()
        self.assertEqual(m.host,"mojplaywin.com")
        self.assertEqual(m.tenant_id,"mojplaywin_site")
        self.assertEqual(m.receiver,FIRST)

    def test_02_second_site_has_a_separate_wallet(self):
        m=self.lookup("zomorodmelal.ir")
        self.assertEqual(m.receiver,SECOND)
        self.assertNotEqual(m.receiver,self.lookup().receiver)

    def test_03_both_synthetic_receivers_have_valid_native_checksum(self):
        self.assertTrue(address_hex(FIRST).startswith("41"))
        self.assertTrue(address_hex(SECOND).startswith("41"))
        self.assertNotEqual(address_hex(FIRST),address_hex(SECOND))

    def test_04_one_explicit_site_is_permitted(self):
        self.assertEqual(self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",FIRST)}).tenant_id,"mojplaywin_site")

    def test_05_unknown_sibling_is_never_inherited(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("shop.mojplaywin.com")

    def test_06_explicit_owned_subsite_may_have_unique_wallet(self):
        single={"shop.mojplaywin.com":row("shop_mpw",SECOND)}
        self.assertEqual(self.lookup("shop.mojplaywin.com",single).tenant_id,"shop_mpw")

    def test_07_external_host_denied_even_if_entry_present(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("rogue.attacker.net",{"rogue.attacker.net":row("host_rogue",SECOND)})

    def test_08_host_lookalike_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("mojplaywin.com.attacker.net")

    def test_09_same_receiver_two_tenants_is_denied(self):
        r=dict(self.registry)
        r["zomorodmelal.ir"]=row("zomorodmelal_site",FIRST)
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry=r)

    def test_10_duplicate_tenant_id_two_wallets_denied(self):
        r=dict(self.registry)
        r["zomorodmelal.ir"]=row("mojplaywin_site",SECOND)
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry=r)

    def test_11_unapproved_boolean_false_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",FIRST,approved=False)})

    def test_12_truthy_approval_string_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",FIRST,approved="yes")})

    def test_13_wrong_asset_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",FIRST,asset="USDT")})

    def test_14_wrong_network_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",FIRST,network="tron-testnet")})

    def test_15_invalid_receiver_checksum_denied(self):
        bad=FIRST[:-1]+("1" if FIRST[-1]!="1" else "2")
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",bad)})

    def test_16_receiver_nonstring_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("mojplaywin_site",[])})

    def test_17_duplicate_field_extra_denied(self):
        r=row("mojplaywin_site",FIRST);r["redirect"]="http://attacker.net"
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":r})

    def test_18_empty_registry_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={})

    def test_19_list_registry_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry=[row("a_site",FIRST)])

    def test_20_uppercase_host_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("MOJPLAYWIN.COM")

    def test_21_host_with_port_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("mojplaywin.com:443")

    def test_22_tenant_id_invalid_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry={"mojplaywin.com":row("INVALID ID",FIRST)})

    def test_23_wildcard_host_denied(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("*.mojplaywin.com")

    def test_24_too_many_hosts_denied(self):
        r={f"shop{i}.mojplaywin.com":row(f"site_{i:02d}",FIRST) for i in range(65)}
        with self.assertRaises(MerchantConfigurationError):
            self.lookup(registry=r)

    def test_25_unregistered_host_cannot_reuse_existing_wallet(self):
        with self.assertRaises(MerchantConfigurationError):
            self.lookup("new.mojplaywin.com",self.registry)

    def test_26_an_invoice_receiver_cannot_be_inferred_from_brand(self):
        m=self.lookup()
        self.assertFalse(hasattr(m,"signal_brand"))
        self.assertEqual(m.chain,"tron-mainnet")
        self.assertEqual(m.asset,"TRX")

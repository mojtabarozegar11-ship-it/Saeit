import unittest
from types import SimpleNamespace
from services.mpw_trx_walletless_core import PaymentHold,SolidifiedTransfer
from services.mpw_walletless_django_test_bridge import (
    _test_only_guard,settle_to_django_test_database,
    unpaid_owner_safe_status,TrustedNodePair,
)

class DjangoIntegrationGuards(unittest.TestCase):
    def test_real_database_refused_even_if_all_other_flags_true(self):
        settings=SimpleNamespace(MPW_WALLETLESS_TRX_TEST_ADAPTER=True,
           MPW_COMMERCE_INVOICING_ENABLED=False,MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
        for name in ("zomorod2_sites_main","production","", "walletless_ci"):
            db=SimpleNamespace(vendor="mysql",settings_dict={"NAME":name})
            with self.subTest(name=name),self.assertRaises(PaymentHold):
                _test_only_guard(settings,db)

    def test_test_connection_requires_all_off_switches(self):
        db=SimpleNamespace(vendor="mysql",settings_dict={"NAME":"test_walletless_isolated"})
        for bad in ("MPW_WALLETLESS_TRX_TEST_ADAPTER","MPW_COMMERCE_INVOICING_ENABLED","MPW_WALLETLESS_TRX_PUBLIC_ENABLED"):
            kwargs=dict(MPW_WALLETLESS_TRX_TEST_ADAPTER=True,
                        MPW_COMMERCE_INVOICING_ENABLED=False,
                        MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
            kwargs[bad]=False if bad.endswith("TEST_ADAPTER") else True
            with self.subTest(flag=bad),self.assertRaises(PaymentHold):
                _test_only_guard(SimpleNamespace(**kwargs),db)

    def test_wrong_database_backend_fails_closed(self):
        flags=SimpleNamespace(MPW_WALLETLESS_TRX_TEST_ADAPTER=True,
                     MPW_COMMERCE_INVOICING_ENABLED=False,MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
        db=SimpleNamespace(vendor="sqlite",settings_dict={"NAME":"test_payment"})
        with self.assertRaises(PaymentHold):_test_only_guard(flags,db)

    def test_schema_guard_allows_test_only_without_writing(self):
        flags=SimpleNamespace(MPW_WALLETLESS_TRX_TEST_ADAPTER=True,
                    MPW_COMMERCE_INVOICING_ENABLED=False,MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
        db=SimpleNamespace(vendor="mysql",settings_dict={"NAME":"test_walletless_mariadb"})
        self.assertIsNone(_test_only_guard(flags,db))

    def test_no_invoice_id_or_no_verified_pair_fails_before_django_import(self):
        for invoice in (0,-1,"123",True):
            with self.subTest(id=invoice),self.assertRaises(PaymentHold):
                settle_to_django_test_database(invoice,"a"*64,
                   TrustedNodePair("a","b",lambda x:None,lambda x:None,True))
        with self.assertRaises(PaymentHold):
            settle_to_django_test_database(1,"a"*64,object())

    def test_paid_owner_only_with_three_independent_grants(self):
        yes=unpaid_owner_safe_status(customer_id=50,order_owner_id=50,
             invoice_status="paid",has_verified_ledger=True,has_ready_fulfillment=True)
        self.assertEqual(yes,{"status":"paid","can_download":True})
        for pair in (
            (51,50,"paid",True,True),
            (50,50,"awaiting",True,True),
            (50,50,"paid",False,True),
            (50,50,"paid",True,False),
            (0,50,"paid",True,True),
        ):
            with self.subTest(case=pair):
                v=unpaid_owner_safe_status(
                    customer_id=pair[0],order_owner_id=pair[1],invoice_status=pair[2],
                    has_verified_ledger=pair[3],has_ready_fulfillment=pair[4])
                self.assertFalse(v["can_download"])

if __name__=="__main__":unittest.main()

"""Isolated two-operator finalized-TRX quorum; no RPC, keys or funds used."""
import copy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from mpw_tron_pro.core import tron_address_hex
from moj_commerce.quorum_verifier import TrustedSoliditySource, verify_two_source_finalized_trx
from moj_commerce.services import CommerceUnavailable
from tests.test_moj_commerce_tron_verifier import address, TX


class IndependentSolidityQuorumTests(SimpleTestCase):
    def setUp(self):
        recipient, sender = address(101), address(202)
        start = timezone.now()-timedelta(seconds=40)
        self.block_ms = int((start+timedelta(seconds=20)).timestamp()*1000)
        self.purchase = SimpleNamespace(
            network='tron-mainnet', destination=SimpleNamespace(address=recipient),
            amount_sun=12_500_000, created_at=start,
            expires_at=start+timedelta(minutes=10))
        self.event = {'currency':'TRX','network':'tron-mainnet',
                      'txid':TX,'block_number':998877,'paid_ms':self.block_ms}
        self.body = {'txID':TX,'ret':[{'contractRet':'SUCCESS'}],
            'raw_data':{'contract':[{'type':'TransferContract',
                'parameter':{'type_url':'type.googleapis.com/protocol.TransferContract',
                             'value':{'owner_address':tron_address_hex(sender),
                                      'to_address':tron_address_hex(recipient),
                                      'amount':12_500_000}}}]}}
        self.receipt = {'id':TX,'blockNumber':998877,'blockTimeStamp':self.block_ms,
                        'receipt':{'result':'SUCCESS'}}
        self.first = Mock(return_value=(copy.deepcopy(self.body),copy.deepcopy(self.receipt)))
        self.second = Mock(return_value=(copy.deepcopy(self.body),copy.deepcopy(self.receipt)))

    def sources(self):
        return (TrustedSoliditySource('operator_alpha', self.first, 'a-fake-ci-key'),
                TrustedSoliditySource('operator_beta', self.second, 'b-fake-ci-key'))

    def test_two_independent_trusted_reads_are_required(self):
        result = verify_two_source_finalized_trx(
            self.event,self.purchase,sources=self.sources())
        self.assertTrue(result['confirmed'])
        self.assertEqual(result['amount_sun'],12_500_000)
        self.first.assert_called_once_with(TX,api_key='a-fake-ci-key')
        self.second.assert_called_once_with(TX,api_key='b-fake-ci-key')

    def test_unconfigured_quorum_never_delivers(self):
        with override_settings(MOJ_COMMERCE_TRON_QUORUM_SOURCES=None):
            with self.assertRaises(CommerceUnavailable):
                verify_two_source_finalized_trx(self.event,self.purchase)
        self.first.assert_not_called()
        self.second.assert_not_called()

    def test_missing_or_duplicate_operator_rejected_without_network(self):
        a,b = self.sources()
        for bad in ((a,), (a,a),
                    (a,TrustedSoliditySource(a.operator_id,self.second)),
                    (a,TrustedSoliditySource('operator_gamma',self.first))):
            with self.assertRaises(CommerceUnavailable):
                verify_two_source_finalized_trx(self.event,self.purchase,sources=bad)
        self.first.assert_not_called()
        self.second.assert_not_called()

    def test_one_offline_provider_blocks_entitlement(self):
        self.second.side_effect = TimeoutError('SENSITIVE_RPC_TOKEN')
        with self.assertRaises(CommerceUnavailable) as caught:
            verify_two_source_finalized_trx(self.event,self.purchase,sources=self.sources())
        self.assertNotIn('SENSITIVE_RPC_TOKEN',str(caught.exception))

    def test_disagreeing_block_timestamp_or_amount_blocks_entitlement(self):
        altered = copy.deepcopy(self.receipt)
        altered['blockTimeStamp'] += 1000
        self.second.return_value = (copy.deepcopy(self.body),altered)
        with self.assertRaises(CommerceUnavailable):
            verify_two_source_finalized_trx(self.event,self.purchase,sources=self.sources())
        body = copy.deepcopy(self.body)
        body['raw_data']['contract'][0]['parameter']['value']['amount'] += 1
        self.second.return_value = (body,copy.deepcopy(self.receipt))
        with self.assertRaises(CommerceUnavailable):
            verify_two_source_finalized_trx(self.event,self.purchase,sources=self.sources())

    def test_nonfinalized_second_receipt_and_wrong_chain_fail_closed(self):
        self.second.return_value = (copy.deepcopy(self.body), {})
        with self.assertRaises(CommerceUnavailable):
            verify_two_source_finalized_trx(self.event,self.purchase,sources=self.sources())
        self.second.return_value = (copy.deepcopy(self.body),copy.deepcopy(self.receipt))
        with self.assertRaises(CommerceUnavailable):
            verify_two_source_finalized_trx(
                {**self.event,'network':'nile-testnet'},self.purchase,sources=self.sources())

    def test_configuration_rejects_malicious_credentials_and_unknown_fetch(self):
        first = self.sources()[0]
        bad_sources = (
            TrustedSoliditySource('bad name', self.second),
            TrustedSoliditySource('operator_beta', self.second, 'bad\nheader'),
            TrustedSoliditySource('operator_beta', self.second, 'x'*513),
            TrustedSoliditySource('operator_beta', None),
        )
        for bad in bad_sources:
            with self.assertRaises(CommerceUnavailable):
                verify_two_source_finalized_trx(
                    self.event,self.purchase,sources=(first,bad))
        self.first.assert_not_called()

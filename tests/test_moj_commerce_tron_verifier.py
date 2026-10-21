"""Real TRON validation algorithm, synthetic SolidityNode response fixtures.

No mock may be used as a production checker. No funds/network/keys involved.
"""
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from mpw_tron_pro.core import tron_address_hex
from moj_commerce.tron_verifier import independently_verify_finalized_trx
from moj_commerce.services import CommerceRejected, CommerceUnavailable

ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
TX = 'a' * 64


def address(seed):
    data = bytes.fromhex('41' + f'{seed:040x}')
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    n = int.from_bytes(data + checksum, 'big')
    output = ''
    while n:
        n, digit = divmod(n, 58)
        output = ALPHABET[digit] + output
    return output


class FinalizedProofIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.dest = address(101)
        self.sender = address(202)
        self.start = timezone.now() - timedelta(seconds=30)
        self.end = self.start + timedelta(minutes=10)
        self.block_ms = int((self.start + timedelta(seconds=20)).timestamp() * 1000)
        self.order = SimpleNamespace(network='tron-mainnet',
            destination=SimpleNamespace(address=self.dest),
            amount_sun=12_500_000, created_at=self.start, expires_at=self.end)
        self.event = dict(currency='TRX', network='tron-mainnet', txid=TX,
                          block_number=998877, paid_ms=self.block_ms)
        self.body = dict(txID=TX, ret=[{'contractRet':'SUCCESS'}], raw_data={
            'contract':[{'type':'TransferContract','parameter':{
                'type_url':'type.googleapis.com/protocol.TransferContract',
                'value':{'owner_address':tron_address_hex(self.sender),
                         'to_address':tron_address_hex(self.dest), 'amount':12_500_000}}}]})
        self.receipt = dict(id=TX, blockNumber=998877, blockTimeStamp=self.block_ms,
                            receipt={'result':'SUCCESS'})

    def verify(self, body=None, receipt=None, event=None, order=None):
        fake = Mock(return_value=(body if body is not None else self.body,
                                  receipt if receipt is not None else self.receipt))
        result = independently_verify_finalized_trx(event or self.event, order or self.order, fetch=fake)
        self.assert_called = fake
        return result

    def test_server_reads_chain_and_returns_exact_proof(self):
        with override_settings(MOJ_COMMERCE_TRONGRID_API_KEY='fake-ci-key-not-real'):
            proof = self.verify()
        self.assertEqual(proof, {
            'confirmed':True, 'destination':self.dest, 'amount_sun':12500000,
            'txid':TX, 'network':'tron-mainnet', 'block_number':998877,
        })
        self.assert_called.assert_called_once_with(TX, api_key='fake-ci-key-not-real')

    def test_wrong_recipient_rejected(self):
        import copy
        body = copy.deepcopy(self.body)
        body['raw_data']['contract'][0]['parameter']['value']['to_address'] = tron_address_hex(self.sender)
        with self.assertRaises(CommerceRejected): self.verify(body=body)

    def test_wrong_amount_rejected(self):
        import copy
        body = copy.deepcopy(self.body)
        body['raw_data']['contract'][0]['parameter']['value']['amount'] -= 1
        with self.assertRaises(CommerceRejected): self.verify(body=body)

    def test_unsolidified_receipt_rejected(self):
        with self.assertRaises(CommerceRejected): self.verify(receipt={})

    def test_failure_receipt_rejected(self):
        with self.assertRaises(CommerceRejected): self.verify(receipt={**self.receipt, 'receipt':{'result':'FAILED'}})

    def test_wrong_block_number_in_event_rejected(self):
        with self.assertRaises(CommerceRejected): self.verify(event={**self.event,'block_number':999999})

    def test_wrong_paid_timestamp_in_event_rejected(self):
        with self.assertRaises(CommerceRejected): self.verify(event={**self.event,'paid_ms':self.block_ms + 1000})

    def test_wrong_network_rejected_before_rpc(self):
        with self.assertRaises(CommerceRejected): self.verify(event={**self.event,'network':'nile-testnet'})

    def test_malformed_receive_address_rejected(self):
        bad = SimpleNamespace(**{**vars(self.order), 'destination':SimpleNamespace(address='T'+'A'*33)})
        with self.assertRaises(CommerceRejected): self.verify(order=bad)

    def test_unreachable_rpc_does_not_mark_paid(self):
        def offline(*args, **kwargs): raise TimeoutError('rpc down')
        with self.assertRaises(CommerceUnavailable):
            independently_verify_finalized_trx(self.event,self.order,fetch=offline)

    def test_nonfinalized_grace_window_is_not_payment(self):
        old = {**self.receipt, 'blockTimeStamp':int((self.end + timedelta(minutes=4)).timestamp()*1000)}
        with self.assertRaises(CommerceRejected): self.verify(receipt=old)
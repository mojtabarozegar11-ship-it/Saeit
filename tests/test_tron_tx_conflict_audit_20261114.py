"""Zero-network/zero-Django immutable TRON evidence conflict scanner tests."""
import unittest
from core.tron_tx_conflict_audit import canonical_txid, ledger_txid, summarize_tron_conflicts

TX = 'a'*64
TX2 = 'b'*64

def ev(tx=TX, provider='zomorod_tron_mainnet_v1', status='processed'):
    return {'event_id': tx, 'provider':provider, 'status':status}

def cr(tx=TX, prefix='tron-mainnet:'):
    return {'reference':prefix+tx}

class TxConflictEvidenceTests(unittest.TestCase):
    def scan(self, e, c, complete=True):
        return summarize_tron_conflicts(e,c,complete=complete)
    def test_empty_complete_snapshot_has_no_conflicts(self):
        self.assertTrue(self.scan([],[])['no_conflicts_in_bounded_snapshot'])
    def test_clean_new_provider_pair(self):
        self.assertEqual(self.scan([ev()],[cr()])['finding_count'],0)
    def test_clean_old_provider_pair(self):
        self.assertEqual(self.scan([ev(provider='mpw_walletless_trx_v1')],[cr(prefix='walletless:tron-mainnet:')])['finding_count'],0)
    def test_canonical_lowercase(self):
        self.assertEqual(canonical_txid(TX.upper()),TX)
    def test_ledger_lowercase(self):
        self.assertEqual(ledger_txid('TRON-MAINNET:'+TX.upper()),TX)
    def test_legacy_ledger_uppercase(self):
        self.assertEqual(ledger_txid('WALLETLESS:TRON-MAINNET:'+TX.upper()),TX)
    def test_reject_bad_hash_length(self):
        self.assertIsNone(canonical_txid('a'*63))
    def test_reject_bad_hash_chars(self):
        self.assertIsNone(canonical_txid('z'*64))
    def test_reject_input_bool(self):
        self.assertIsNone(canonical_txid(True))
    def test_reject_ref_unrelated_network(self):
        self.assertIsNone(ledger_txid('bitcoin:'+TX))
    def test_reject_ref_suffix(self):
        self.assertIsNone(ledger_txid('tron-mainnet:'+TX+':junk'))
    def test_reject_ref_bytes(self):
        self.assertIsNone(ledger_txid(b'tron-mainnet:'+TX.encode()))
    def test_event_only(self):
        self.assertIn('event_without_credit',self.scan([ev()],[])['findings'][0]['flags'])
    def test_credit_only(self):
        self.assertIn('credit_without_event',self.scan([],[cr()])['findings'][0]['flags'])
    def test_duplicate_events_across_providers(self):
        x=self.scan([ev(),ev(provider='mpw_walletless_trx_v1')],[cr()])
        self.assertIn('cross_provider_event',x['findings'][0]['flags'])
        self.assertIn('multiple_finalized_events',x['findings'][0]['flags'])
    def test_duplicate_events_same_provider(self):
        self.assertIn('multiple_finalized_events',self.scan([ev(),ev()],[cr()])['findings'][0]['flags'])
    def test_duplicate_credits_mixed_prefix(self):
        x=self.scan([ev()],[cr(),cr(prefix='walletless:tron-mainnet:')])
        self.assertIn('multiple_ledger_credits',x['findings'][0]['flags'])
    def test_duplicate_credits_case_insensitive(self):
        x=self.scan([ev()],[cr(),cr(tx=TX.upper())])
        self.assertEqual(x['findings'][0]['credits'],2)
    def test_unprocessed_event(self):
        self.assertIn('unprocessed_event',self.scan([ev(status='received')],[cr()])['findings'][0]['flags'])
    def test_invalid_event_id_counts(self):
        self.assertEqual(self.scan([ev(tx='abc')],[])['invalid_event_txids'],1)
    def test_invalid_ledger_reference_counts(self):
        self.assertEqual(self.scan([],[cr(tx='abc')])['invalid_credit_refs'],1)
    def test_invalid_event_fails_clean(self):
        self.assertFalse(self.scan([ev(tx='abc')],[])['no_conflicts_in_bounded_snapshot'])
    def test_invalid_credit_fails_clean(self):
        self.assertFalse(self.scan([],[cr(tx='abc')])['no_conflicts_in_bounded_snapshot'])
    def test_incomplete_scan_never_clean(self):
        self.assertFalse(self.scan([ev()],[cr()],complete=False)['no_conflicts_in_bounded_snapshot'])
    def test_production_never_safe_claim(self):
        self.assertFalse(self.scan([ev()],[cr()])['production_payment_safe'])
    def test_complete_must_be_bool(self):
        with self.assertRaises(ValueError): self.scan([],[],complete=1)
    def test_fingerprint_hides_txid(self):
        x=self.scan([ev()],[])['findings'][0]
        self.assertNotIn(TX,str(x))
        self.assertEqual(len(x['fingerprint']),16)
    def test_distinct_txid_counts(self):
        x=self.scan([ev(TX),ev(TX2)],[cr(TX),cr(TX2)])
        self.assertEqual(x['distinct_txids'],2)
    def test_duplicate_event_case_canonicalized(self):
        self.assertEqual(self.scan([ev(),ev(TX.upper())],[cr()])['findings'][0]['events'],2)
    def test_results_sorted_by_txid(self):
        x=self.scan([ev(TX2),ev(TX)],[cr(TX2),cr(TX)])
        self.assertEqual(x['finding_count'],0)
    def test_malformed_event_dict(self):
        self.assertEqual(self.scan([None],[])['invalid_event_txids'],1)
    def test_malformed_credit_dict(self):
        self.assertEqual(self.scan([],[None])['invalid_credit_refs'],1)
    def test_isolated_unknown_payment_event_does_not_expand_credit(self):
        x=self.scan([ev(TX),ev(TX2)],[cr(TX)])
        self.assertEqual(x['finding_count'],1)
    def test_scanned_counts(self):
        x=self.scan([ev(),ev(TX2)],[cr()])
        self.assertEqual((x['scanned_events'],x['scanned_credits']),(2,1))

if __name__=='__main__': unittest.main()

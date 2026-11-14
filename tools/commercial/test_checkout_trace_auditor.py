import unittest
from checkout_trace_auditor import audit_checkout_trace
ORDER='a'*64
PAY='b'*64

def event(event_id,kind,source='client',payment_ref='',amount='10.00'):
    return {'event_id':event_id,'order_ref':ORDER,'event':kind,'source':source,'amount':amount,'currency':'USD','payment_ref':payment_ref}

def payload(events):return {'schema_version':1,'events':events}

class CheckoutTraceTests(unittest.TestCase):
    def test_one_legitimate_flow_without_structural_errors(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),event('e3','fulfilled','server')]
        result=audit_checkout_trace(payload(events))
        self.assertEqual(result['issues_count'],0)
        self.assertEqual(result['orders'][0]['status'],'NO_STRUCTURAL_ISSUES')
        self.assertIn('NOT_PAYMENT_OR_DELIVERY_PROOF',result['report_scope'])
    def test_client_side_payment_claim_does_not_authorize_delivery(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','client'),event('e3','fulfilled','server')]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('PAYMENT_NOT_GATEWAY_ATTESTED_IN_TRACE',issues)
        self.assertIn('FULFILLMENT_WITHOUT_TRUSTED_PAYMENT_IN_TRACE',issues)
    def test_duplicate_fulfillment_is_detected(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),event('e3','fulfilled','server'),event('e4','fulfilled','server')]
        self.assertIn('MULTIPLE_FULFILLMENTS',audit_checkout_trace(payload(events))['orders'][0]['issues'])
    def test_exact_webhook_replay_is_ignored(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),event('e2','payment_confirmed','gateway',PAY),event('e3','fulfilled','server')]
        result=audit_checkout_trace(payload(events))
        self.assertEqual(result['replayed_events_ignored'],1)
        self.assertEqual(result['issues_count'],0)
    def test_payment_failure_after_confirmation_is_ambiguous_and_flagged(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),
                event('e3','payment_failed','gateway'),event('e4','fulfilled','server')]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('FAILURE_AFTER_CONFIRMATION_REQUIRES_REVIEW',issues)
    def test_failed_attempt_before_later_valid_confirmation_is_allowed(self):
        events=[event('e1','checkout_created'),event('e2','payment_failed','gateway'),
                event('e3','payment_confirmed','gateway',PAY),event('e4','fulfilled','server')]
        self.assertEqual(audit_checkout_trace(payload(events))['issues_count'],0)
    def test_payment_before_created_is_detected(self):
        events=[event('e1','payment_confirmed','gateway',PAY),event('e2','checkout_created'),event('e3','fulfilled','server')]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('PAYMENT_BEFORE_CHECKOUT_CREATION',issues)
        self.assertIn('CHECKOUT_CREATION_AFTER_PAYMENT_OR_DELIVERY',issues)
    def test_normal_lifecycle_order_has_no_ordering_issue(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),event('e3','fulfilled','server')]
        self.assertEqual(audit_checkout_trace(payload(events))['issues_count'],0)
    def test_refund_after_delivery_flags_entitlement_review(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),
                event('e3','fulfilled','server'),event('e4','refund_confirmed','gateway',PAY)]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('REFUND_AFTER_FULFILLMENT_ACCESS_REVIEW',issues)
    def test_refund_before_any_verified_payment_is_suspicious(self):
        events=[event('e1','checkout_created'),event('e2','refund_confirmed','gateway',PAY)]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('REFUND_WITHOUT_MATCHED_GATEWAY_PAYMENT',issues)
    def test_delivery_after_refund_flags_review(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),
                event('e3','refund_confirmed','gateway',PAY),event('e4','fulfilled','server')]
        issues=audit_checkout_trace(payload(events))['orders'][0]['issues']
        self.assertIn('FULFILLMENT_AFTER_REFUND_REQUIRES_REVIEW',issues)
    def test_paid_but_no_fulfillment_is_not_declared_clean(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY)]
        result=audit_checkout_trace(payload(events))
        self.assertIn('PAYMENT_WITHOUT_FULFILLMENT_IN_TRACE',result['orders'][0]['issues'])
    def test_unpaid_started_checkout_is_not_false_missing_fulfillment(self):
        result=audit_checkout_trace(payload([event('e1','checkout_created')]))
        self.assertNotIn('PAYMENT_WITHOUT_FULFILLMENT_IN_TRACE',result['orders'][0]['issues'])
    def test_id_collision_with_changed_payload_is_detected(self):
        events=[event('e1','checkout_created'),event('e1','fulfilled','server')]
        self.assertIn('EVENT_ID_COLLISION',audit_checkout_trace(payload(events))['orders'][0]['issues'])
    def test_amount_mutation_detected(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY,amount='11.00')]
        self.assertIn('ORDER_AMOUNT_OR_CURRENCY_CHANGED',audit_checkout_trace(payload(events))['orders'][0]['issues'])
    def test_multiple_payment_references_flag_possible_double_charge(self):
        events=[event('e1','checkout_created'),event('e2','payment_confirmed','gateway',PAY),event('e3','payment_confirmed','gateway','c'*64)]
        self.assertIn('POSSIBLE_MULTIPLE_PAYMENT_REFERENCES',audit_checkout_trace(payload(events))['orders'][0]['issues'])
    def test_personal_card_data_column_is_refused(self):
        e=event('e1','checkout_created');e['card_number']='4111111111111111'
        with self.assertRaisesRegex(ValueError,'unknown fields'):audit_checkout_trace(payload([e]))
    def test_unhashed_payment_reference_is_refused(self):
        with self.assertRaisesRegex(ValueError,'SHA-256'):audit_checkout_trace(payload([event('e1','payment_confirmed','gateway','raw_tx_id')]))
    def test_nonfinite_amount_rejected(self):
        with self.assertRaisesRegex(ValueError,'amount'):audit_checkout_trace(payload([event('e1','checkout_created',amount='NaN')]))
if __name__=='__main__':unittest.main()

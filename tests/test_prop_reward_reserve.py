import unittest

from prop_firm.reward_reserve import (
    RewardReserveLedger, SUN_PER_TRX,
)


class RewardReserveTests(unittest.TestCase):
    def test_first_purchase_allocates_eighty_percent(self):
        ledger = RewardReserveLedger()
        a = ledger.allocate_after_settlement(
            order_id="o1", fee_sun=30 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        self.assertEqual(a.reward_reserve_sun, 24 * SUN_PER_TRX)
        self.assertEqual(a.refund_reserve_sun, 3 * SUN_PER_TRX)
        self.assertEqual(a.operating_buffer_sun, 3 * SUN_PER_TRX)
        self.assertEqual(a.maximum_reward_sun, 24 * SUN_PER_TRX)

    def test_retry_allocates_its_own_reserve(self):
        ledger = RewardReserveLedger()
        a = ledger.allocate_after_settlement(
            order_id="retry", fee_sun=18 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        self.assertEqual(a.reward_reserve_sun, 14_400_000)
        self.assertEqual(ledger.available_reward_reserve_sun, 14_400_000)

    def test_unsettled_payment_cannot_create_reserve(self):
        with self.assertRaisesRegex(ValueError, "settled"):
            RewardReserveLedger().allocate_after_settlement(
                order_id="o1", fee_sun=30 * SUN_PER_TRX,
                settlement_confirmed=False,
            )

    def test_duplicate_allocation_rejected(self):
        ledger = RewardReserveLedger()
        ledger.allocate_after_settlement(
            order_id="o1", fee_sun=30 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ledger.allocate_after_settlement(
                order_id="o1", fee_sun=30 * SUN_PER_TRX,
                settlement_confirmed=True,
            )

    def test_reward_is_limited_to_order_reserve(self):
        ledger = RewardReserveLedger()
        ledger.allocate_after_settlement(
            order_id="o1", fee_sun=30 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            ledger.commit_reward(order_id="o1", amount_sun=24 * SUN_PER_TRX + 1)

    def test_reward_commitment_is_real_and_bounded(self):
        ledger = RewardReserveLedger()
        ledger.allocate_after_settlement(
            order_id="o1", fee_sun=30 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        ledger.commit_reward(order_id="o1", amount_sun=10 * SUN_PER_TRX)
        self.assertEqual(ledger.available_reward_reserve_sun, 14 * SUN_PER_TRX)

    def test_unknown_order_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            RewardReserveLedger().commit_reward(
                order_id="missing", amount_sun=1,
            )

    def test_virtual_principal_is_zero(self):
        ledger = RewardReserveLedger()
        ledger.allocate_after_settlement(
            order_id="o1", fee_sun=30 * SUN_PER_TRX,
            settlement_confirmed=True,
        )
        self.assertEqual(ledger.snapshot()["virtual_principal_requirement_sun"], 0)

    def test_zero_amount_rejected(self):
        with self.assertRaises(ValueError):
            RewardReserveLedger().commit_reward(order_id="x", amount_sun=0)


if __name__ == "__main__":
    unittest.main()

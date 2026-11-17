"""No payout or broker transfer: exact-Decimal Plan 1 realized-profit previews."""
from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest
from prop_firm.plan1_owner_account_profit_preview import (
    preview_realized_profit_split, preview_separate_crypto_payout,
)

PERIOD = "PERIOD-ABCDEFGHIJKLMNOP"

def profit(net="100", loss="0"):
    return preview_realized_profit_split(
        period_ref=PERIOD, realized_net_attributable_usd=Decimal(net),
        previous_loss_carry_usd=Decimal(loss))

def quote(p=None, rate="1", fee="0.1"):
    return preview_separate_crypto_payout(
        profit_preview=profit() if p is None else p,
        asset="TRX", network="TRON-mainnet",
        asset_units_per_usd_net_conversion=Decimal(rate),
        transfer_fee_asset_units=Decimal(fee))

class RealizedProfitSplitPreviewTests(unittest.TestCase):
    def test_basic_trader_seventy_percent_usd(self):
        self.assertEqual(profit().trader_gross_share_usd,Decimal("70.00"))

    def test_basic_company_thirty_percent_usd(self):
        self.assertEqual(profit().organizer_gross_share_usd,Decimal("30.00"))

    def test_exact_profit_conservation(self):
        p=profit("333.33")
        self.assertEqual(p.trader_gross_share_usd+p.organizer_gross_share_usd,
                         p.distributable_profit_usd)

    def test_no_realized_profit_no_trader_share(self):
        self.assertEqual(profit("0").trader_gross_share_usd,Decimal("0.00"))

    def test_negative_realized_period_no_trader_share(self):
        self.assertEqual(profit("-50").trader_gross_share_usd,Decimal("0.00"))

    def test_negative_period_adds_to_loss_carry(self):
        self.assertEqual(profit("-50","20").new_loss_carry_usd,Decimal("70"))

    def test_positive_profit_first_offsets_past_loss(self):
        self.assertEqual(profit("100","40").eligible_positive_profit_usd,
                         Decimal("60"))

    def test_prior_loss_carry_can_zero_out_profit(self):
        self.assertEqual(profit("40","100").trader_gross_share_usd,Decimal("0.00"))

    def test_new_loss_carry_after_partial_recovery(self):
        self.assertEqual(profit("40","100").new_loss_carry_usd,Decimal("60"))

    def test_no_prior_loss_after_profitable_period(self):
        self.assertEqual(profit("100","20").new_loss_carry_usd,Decimal("0"))

    def test_no_fractional_cent_distributed(self):
        p=profit("0.0099")
        self.assertEqual(p.distributable_profit_usd,Decimal("0.00"))
        self.assertEqual(p.rounding_reserve_usd,Decimal("0.0099"))

    def test_cents_remainder_tracked(self):
        p=profit("100.0011")
        self.assertEqual(p.rounding_reserve_usd,Decimal("0.0011"))

    def test_trader_share_rounded_down_to_cent(self):
        self.assertEqual(profit("0.03").trader_gross_share_usd,Decimal("0.02"))

    def test_company_gets_remainder_to_conserve_usd(self):
        self.assertEqual(profit("0.03").organizer_gross_share_usd,Decimal("0.01"))

    def test_unique_period_identifier_required(self):
        with self.assertRaises(ValueError):
            preview_realized_profit_split(
                period_ref="unknown",
                realized_net_attributable_usd=Decimal("1"),
                previous_loss_carry_usd=Decimal("0"))

    def test_float_realized_usd_rejected(self):
        with self.assertRaises(ValueError):
            preview_realized_profit_split(period_ref=PERIOD,
                 realized_net_attributable_usd=1.0,
                 previous_loss_carry_usd=Decimal("0"))

    def test_missing_loss_carry_rejected(self):
        with self.assertRaises(ValueError):
            preview_realized_profit_split(period_ref=PERIOD,
                 realized_net_attributable_usd=Decimal("1"),
                 previous_loss_carry_usd=None)

    def test_negative_previous_loss_carry_rejected(self):
        with self.assertRaises(ValueError):
            profit("100","-1")

    def test_nan_profit_rejected(self):
        with self.assertRaises(ValueError):
            profit("NaN")

    def test_infinite_profit_rejected(self):
        with self.assertRaises(ValueError):
            profit("Infinity")

    def test_excess_profit_precision_rejected(self):
        with self.assertRaises(ValueError):
            profit("0.00001")

    def test_source_is_not_authenticated_broker_statement(self):
        self.assertFalse(profit().actual_broker_trade_reconciliation_verified)

    def test_source_is_not_verified_period_close(self):
        self.assertFalse(profit().period_close_independently_verified)

    def test_source_is_not_legal_payout_approval(self):
        self.assertFalse(profit().buyer_share_legally_due_verified)

    def test_source_never_issues_invoice(self):
        self.assertFalse(profit().invoice_issued)

    def test_source_never_sends_principal(self):
        self.assertFalse(profit().trading_principal_sent_to_buyer)

    def test_source_never_authorizes_crypto_payment(self):
        self.assertFalse(profit().crypto_payout_authorized)

    def test_source_never_sends_chain_transaction(self):
        self.assertFalse(profit().onchain_transfer_executed)

    def test_preview_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            profit().crypto_payout_authorized=True

class SeparateCryptoPaymentPreviewTests(unittest.TestCase):
    def test_trx_quote_before_fee_is_seventy(self):
        self.assertEqual(quote().crypto_gross_before_transfer_fee,Decimal("70.00000000"))

    def test_only_transfer_fee_deducted_from_trader_share(self):
        self.assertEqual(quote().crypto_net_after_transfer_fee,Decimal("69.90000000"))

    def test_company_share_untouched_by_transfer_fee(self):
        self.assertEqual(profit().organizer_gross_share_usd,Decimal("30.00"))

    def test_quote_uses_explicit_buyer_asset_and_network(self):
        q=quote()
        self.assertEqual((q.asset,q.network),("TRX","TRON-mainnet"))

    def test_quote_supports_other_crypto_only_as_display(self):
        q=preview_separate_crypto_payout(
            profit_preview=profit(),asset="USDT",network="TRON-TRC20",
            asset_units_per_usd_net_conversion=Decimal("0.998"),
            transfer_fee_asset_units=Decimal("1"))
        self.assertEqual(q.asset,"USDT")
        self.assertFalse(q.crypto_payout_authorized)

    def test_no_profit_no_fee_yields_zero_transfer(self):
        self.assertEqual(quote(profit("0"),rate="1",fee="0").crypto_net_after_transfer_fee,
                         Decimal("0E-8"))

    def test_fee_exceeding_profit_is_not_auto_charged(self):
        with self.assertRaises(ValueError):
            quote(profit("1"),rate="1",fee="1")

    def test_fee_equal_to_proceeds_yields_zero_not_negative(self):
        q=quote(profit("1"),rate="1",fee="0.7")
        self.assertEqual(q.crypto_net_after_transfer_fee,Decimal("0E-8"))

    def test_negative_crypto_fee_rejected(self):
        with self.assertRaises(ValueError):
            quote(fee="-0.1")

    def test_invalid_rate_zero_rejected(self):
        with self.assertRaises(ValueError):
            quote(rate="0")

    def test_negative_fx_rate_rejected(self):
        with self.assertRaises(ValueError):
            quote(rate="-1")

    def test_fx_rate_as_float_rejected(self):
        with self.assertRaises(ValueError):
            preview_separate_crypto_payout(profit_preview=profit(),asset="TRX",
                network="TRON-mainnet",asset_units_per_usd_net_conversion=1.25,
                transfer_fee_asset_units=Decimal("0"))

    def test_crypto_fee_as_float_rejected(self):
        with self.assertRaises(ValueError):
            preview_separate_crypto_payout(profit_preview=profit(),asset="TRX",
                network="TRON-mainnet",asset_units_per_usd_net_conversion=Decimal("1"),
                transfer_fee_asset_units=0.5)

    def test_nan_rate_rejected(self):
        with self.assertRaises(ValueError):
            quote(rate="NaN")

    def test_fee_has_eight_digit_precision_limit(self):
        with self.assertRaises(ValueError):
            quote(fee="0.000000001")

    def test_rate_has_eight_digit_precision_limit(self):
        with self.assertRaises(ValueError):
            quote(rate="0.000000001")

    def test_invalid_network_rejected(self):
        with self.assertRaises(ValueError):
            preview_separate_crypto_payout(profit_preview=profit(),
                asset="TRX",network="../../wallet",
                asset_units_per_usd_net_conversion=Decimal("1"),
                transfer_fee_asset_units=Decimal("0"))

    def test_invalid_asset_rejected(self):
        with self.assertRaises(ValueError):
            preview_separate_crypto_payout(profit_preview=profit(),
                asset="UNKNOWN TOKEN",network="TRON-mainnet",
                asset_units_per_usd_net_conversion=Decimal("1"),
                transfer_fee_asset_units=Decimal("0"))

    def test_nonprofit_preview_is_rejected(self):
        with self.assertRaises(ValueError):
            preview_separate_crypto_payout(profit_preview=None,
                asset="TRX",network="TRON-mainnet",
                asset_units_per_usd_net_conversion=Decimal("1"),
                transfer_fee_asset_units=Decimal("0"))

    def test_quote_does_not_verify_external_exchange_rate(self):
        self.assertFalse(quote().external_rate_locked_and_verified)

    def test_quote_does_not_verify_chain_transfer_fee(self):
        self.assertFalse(quote().transfer_fee_independently_verified)

    def test_quote_does_not_verify_customer_wallet_ownership(self):
        self.assertFalse(quote().recipient_wallet_independently_verified)

    def test_quote_does_not_claim_company_treasury_funding(self):
        self.assertFalse(quote().company_treasury_funds_settled)

    def test_quote_does_not_withdraw_from_litefinance_to_customer(self):
        self.assertFalse(quote().broker_direct_to_buyer_withdrawal)

    def test_quote_does_not_authorize_crypto_payout(self):
        self.assertFalse(quote().crypto_payout_authorized)

    def test_quote_does_not_sign_or_broadcast_transaction(self):
        self.assertFalse(quote().transfer_signed)
        self.assertFalse(quote().transfer_broadcast)

    def test_crypto_quote_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            quote().transfer_broadcast=True

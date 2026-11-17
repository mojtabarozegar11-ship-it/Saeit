"""MOJ PROP Plan1: source-only reconciliation of owner-account trading profit.

All money remains in the authorized account until independent settlement.
This module DOES NOT withdraw broker funds, fetch an FX rate, pay a wallet,
authorize a crypto transaction, claim an authenticated broker statement or
create a customer payable. Any offer must define settlement period, buyer's
individual attributable realized P&L, fees and prior carried loss in advance.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
import re

CENT = Decimal("0.01")
CRYPTO_QUANTUM = Decimal("0.00000001")
TRADER_RATE = Decimal("0.70")
FIRM_RATE = Decimal("0.30")
PERIOD = re.compile(r"PERIOD-[A-Z0-9]{12,32}\Z")
ASSET = re.compile(r"[A-Z0-9]{2,12}\Z")
NETWORK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,31}\Z")

@dataclass(frozen=True)
class ProfitSharePreview:
    period_ref: str
    realized_net_attributable_usd: Decimal
    previous_loss_carry_usd: Decimal
    new_loss_carry_usd: Decimal
    eligible_positive_profit_usd: Decimal
    distributable_profit_usd: Decimal
    rounding_reserve_usd: Decimal
    trader_gross_share_usd: Decimal
    organizer_gross_share_usd: Decimal
    trading_principal_sent_to_buyer: bool = False
    actual_broker_trade_reconciliation_verified: bool = False
    period_close_independently_verified: bool = False
    buyer_share_legally_due_verified: bool = False
    invoice_issued: bool = False
    crypto_payout_authorized: bool = False
    onchain_transfer_executed: bool = False

@dataclass(frozen=True)
class CryptoPayoutQuotePreview:
    period_ref: str
    asset: str
    network: str
    trader_gross_share_usd: Decimal
    quoted_asset_units_per_usd: Decimal
    crypto_gross_before_transfer_fee: Decimal
    actual_transfer_fee_asset_units_preview: Decimal
    crypto_net_after_transfer_fee: Decimal
    broker_direct_to_buyer_withdrawal: bool = False
    recipient_wallet_independently_verified: bool = False
    transfer_fee_independently_verified: bool = False
    external_rate_locked_and_verified: bool = False
    company_treasury_funds_settled: bool = False
    crypto_payout_authorized: bool = False
    transfer_signed: bool = False
    transfer_broadcast: bool = False


def _amount(value, name, *, allow_negative=False, limit_scale=8):
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError(f"{name} must be a finite exact Decimal")
    if not allow_negative and value < 0:
        raise ValueError(f"{name} cannot be negative")
    if value.as_tuple().exponent < -limit_scale:
        raise ValueError(f"{name} precision exceeds declared scale")
    if abs(value) > Decimal("1000000000000"):
        raise ValueError(f"{name} exceeds source-only bounds")
    return value


def preview_realized_profit_split(
    *, period_ref, realized_net_attributable_usd, previous_loss_carry_usd,
):
    """Apply 70/30 to positive reconciled net period profit after past losses.

    Attributable net P&L must ALREADY include broker spread, swap, commission
    and other contractually allowed trading expenses; no future or floating
    profit may be supplied. Proof and double-payment exclusion are required
    externally and are intentionally NOT supplied by this calculator.
    """
    if type(period_ref) is not str or PERIOD.fullmatch(period_ref) is None:
        raise ValueError("bounded unique settlement period reference required")
    net = _amount(realized_net_attributable_usd, "realized_net_attributable_usd",
                  allow_negative=True, limit_scale=4)
    carry = _amount(previous_loss_carry_usd, "previous_loss_carry_usd",
                    limit_scale=4)
    eligible = max(Decimal("0"), net - carry)
    new_carry = max(Decimal("0"), carry - net)
    allocatable = eligible.quantize(CENT, rounding=ROUND_DOWN)
    rounding_reserve = eligible - allocatable
    trader = (allocatable * TRADER_RATE).quantize(CENT, rounding=ROUND_DOWN)
    organizer = allocatable - trader
    if trader + organizer != allocatable:
        raise ArithmeticError("allocation ledger must conserve distributable profit")
    return ProfitSharePreview(
        period_ref=period_ref,
        realized_net_attributable_usd=net,
        previous_loss_carry_usd=carry,
        new_loss_carry_usd=new_carry,
        eligible_positive_profit_usd=eligible,
        distributable_profit_usd=allocatable,
        rounding_reserve_usd=rounding_reserve,
        trader_gross_share_usd=trader,
        organizer_gross_share_usd=organizer,
    )


def preview_separate_crypto_payout(
    *, profit_preview, asset, network, asset_units_per_usd_net_conversion,
    transfer_fee_asset_units,
):
    """Price preview only, NOT a quote obtained from a service or a payable.

    The exchange rate must ALREADY be net of disclosed conversion charges;
    otherwise it is misleading. The separate chain transfer fee is
    nonnegative and deducted exactly once from the trader's crypto portion.
    Rate/fee/wallet/KYC/treasury authenticity are NOT verified here.
    """
    if type(profit_preview) is not ProfitSharePreview:
        raise ValueError("prior pure independent profit preview required")
    if (type(asset) is not str or ASSET.fullmatch(asset) is None
            or type(network) is not str or NETWORK.fullmatch(network) is None):
        raise ValueError("explicit payout asset and network required")
    rate = _amount(asset_units_per_usd_net_conversion,
                   "asset_units_per_usd_net_conversion",limit_scale=8)
    fee = _amount(transfer_fee_asset_units, "transfer_fee_asset_units",
                  limit_scale=8)
    if rate <= 0:
        raise ValueError("nonzero externally locked rate required")
    gross = (profit_preview.trader_gross_share_usd * rate).quantize(
        CRYPTO_QUANTUM,rounding=ROUND_DOWN)
    if fee > gross:
        raise ValueError("network fee cannot exceed trader's eligible share")
    net = gross-fee
    return CryptoPayoutQuotePreview(
        period_ref=profit_preview.period_ref, asset=asset, network=network,
        trader_gross_share_usd=profit_preview.trader_gross_share_usd,
        quoted_asset_units_per_usd=rate,
        crypto_gross_before_transfer_fee=gross,
        actual_transfer_fee_asset_units_preview=fee,
        crypto_net_after_transfer_fee=net,
    )

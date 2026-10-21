"""MojPlayWin TRON-only, non-custodial checkout primitives.

Payment safety policy: unique merchant-controlled receiving address per invoice;
no seed, private key, signing, withdrawal, or remote transfer APIs.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING

TRON_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
TXID_PATTERN = re.compile(r'^[a-f0-9]{64}$')
SUN = Decimal(1_000_000)
QUOTE_TTL_MS = 10 * 60 * 1000
SOLIDITY_GRACE_MS = 3 * 60 * 1000

class CheckoutError(ValueError):
    """Invalid pricing, attribution, or payment proof; always fail closed."""


def tron_address_hex(address: str) -> str:
    """Validate a mainnet TRON Base58Check address and return its 41-prefixed hex."""
    if not isinstance(address, str) or len(address) != 34 or address[0] != 'T':
        raise CheckoutError('Invalid TRON recipient address')
    number = 0
    for char in address:
        index = TRON_ALPHABET.find(char)
        if index < 0:
            raise CheckoutError('Invalid Base58 alphabet')
        number = number * 58 + index
    try:
        raw = number.to_bytes(25, 'big')
    except OverflowError as exc:
        raise CheckoutError('Invalid Base58 payload') from exc
    address_bytes, checksum = raw[:21], raw[21:]
    expected = hashlib.sha256(hashlib.sha256(address_bytes).digest()).digest()[:4]
    if address_bytes[0] != 0x41 or checksum != expected:
        raise CheckoutError('Invalid TRON address checksum')
    return address_bytes.hex().upper()


def sun_quote(price_usd: str | Decimal, usd_per_trx: str | Decimal) -> int:
    """Always round UP to the next integer Sun; never float or truncate."""
    try:
        usd, rate = Decimal(str(price_usd)), Decimal(str(usd_per_trx))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CheckoutError('Invalid quote') from exc
    if (not usd.is_finite() or not rate.is_finite() or
        not Decimal('0.01') <= usd <= Decimal('100000.00') or
        usd != usd.quantize(Decimal('.01')) or
        not Decimal('0.001') <= rate <= Decimal('100')):
        raise CheckoutError('Quote outside controlled bounds')
    result = int((usd * SUN / rate).to_integral_value(rounding=ROUND_CEILING))
    if result <= 0 or result > 10**13:
        raise CheckoutError('Invoice amount outside TRON transfer bounds')
    return result


@dataclass(frozen=True)
class ExpectedTransfer:
    txid: str
    address: str
    amount_sun: int
    issued_ms: int
    expires_ms: int

    def validate(self) -> None:
        if not isinstance(self.txid, str) or not TXID_PATTERN.fullmatch(self.txid):
            raise CheckoutError('Invalid transaction hash')
        tron_address_hex(self.address)
        if type(self.amount_sun) is not int or not 0 < self.amount_sun <= 10**13:
            raise CheckoutError('Invalid expected amount')
        if (type(self.issued_ms) is not int or type(self.expires_ms) is not int or
            not self.issued_ms < self.expires_ms <= self.issued_ms + QUOTE_TTL_MS):
            raise CheckoutError('Invalid invoice time window')


@dataclass(frozen=True)
class FinalizedProof:
    txid: str
    block_number: int
    block_ms: int
    amount_sun: int
    recipient: str


def inspect_finalized_trx(tx: dict, receipt: dict, expected: ExpectedTransfer) -> FinalizedProof:
    """Requires solidity-node BODY + RECEIPT. Never trusts a customer screenshot.

    A plain TRX TransferContract with exact destination/amount qualifies only
    after both endpoints return a coherent solidified record. Not a TRC20 checker.
    """
    expected.validate()
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        raise CheckoutError('Missing solidified chain records')
    if tx.get('txID') != expected.txid or receipt.get('id') != expected.txid:
        raise CheckoutError('Mismatched transaction identity')
    responses = tx.get('ret')
    if (not isinstance(responses, list) or len(responses) != 1 or
        not isinstance(responses[0], dict) or responses[0].get('contractRet') != 'SUCCESS'):
        raise CheckoutError('Contract execution not successful')
    execution = receipt.get('receipt')
    if not isinstance(execution, dict) or execution.get('result') not in (None, 'SUCCESS'):
        raise CheckoutError('Receipt execution failed')
    if receipt.get('result') == 'FAILED':
        raise CheckoutError('Transaction failed')
    block, block_ms = receipt.get('blockNumber'), receipt.get('blockTimeStamp')
    if type(block) is not int or block <= 0 or type(block_ms) is not int:
        raise CheckoutError('Missing solidified block evidence')
    if not expected.issued_ms - 15_000 <= block_ms <= expected.expires_ms + SOLIDITY_GRACE_MS:
        raise CheckoutError('Payment outside invoice time window')
    raw = tx.get('raw_data')
    if not isinstance(raw, dict):
        raise CheckoutError('Missing transaction body')
    contracts = raw.get('contract')
    if not isinstance(contracts, list) or len(contracts) != 1:
        raise CheckoutError('Unexpected transaction contract count')
    contract = contracts[0]
    if not isinstance(contract, dict) or contract.get('type') != 'TransferContract':
        raise CheckoutError('Not a native TRX transfer')
    parameter = contract.get('parameter')
    if not isinstance(parameter, dict) or parameter.get('type_url') not in (
        None, 'type.googleapis.com/protocol.TransferContract'):
        raise CheckoutError('Wrong TRON transfer contract')
    value = parameter.get('value')
    if not isinstance(value, dict):
        raise CheckoutError('Missing transfer detail')
    try:
        recipient_hex = value['to_address'].upper()
    except (KeyError, AttributeError) as exc:
        raise CheckoutError('Missing recipient') from exc
    if recipient_hex != tron_address_hex(expected.address):
        raise CheckoutError('Payment sent to another recipient')
    if (not isinstance(value.get('owner_address'), str) or
        not re.fullmatch(r'41[a-fA-F0-9]{40}', value['owner_address'])):
        raise CheckoutError('Invalid sender address')
    amount = value.get('amount')
    if type(amount) is not int or not 0 < amount <= 10**13:
        raise CheckoutError('Invalid native TRX transfer amount')
    return FinalizedProof(expected.txid, block, block_ms, amount, expected.address)


def verify_finalized_trx(tx: dict, receipt: dict, expected: ExpectedTransfer) -> FinalizedProof:
    """Accept only exact finalized native TRX, never an under/overpayment."""
    proof = inspect_finalized_trx(tx, receipt, expected)
    if proof.amount_sun != expected.amount_sun:
        raise CheckoutError('Not an exact invoice amount')
    return proof
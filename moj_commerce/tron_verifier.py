"""Independent finalized-TRX check for the MOJ Commerce merchant receiver.

This adapter NEVER trusts the webhook's proof. It queries pinned mainnet
SolidityNode methods again and checks *both* the finalized transaction body and
execution receipt using the existing native-TRX verifier. It does not support
USDT or other contracts and it does not sign or broadcast transactions.

Source presence is not authorization for deployment. The receiver is OFF by
default; wire this callable deliberately only after operational approval.
"""
from __future__ import annotations

from django.conf import settings
from mpw_tron_pro.core import CheckoutError, ExpectedTransfer, verify_finalized_trx
from mpw_tron_pro.rpc import finalized_records
from .services import CommerceRejected, CommerceUnavailable


def independently_verify_finalized_trx(event, purchase, *, fetch=finalized_records):
    """Return a strictly typed proof read from TRON SolidityNode, not event data.

    Network/provider absence => unavailable (retry event); incorrect finalized
    transaction => rejected (never deliver). No paid status is changed here.
    """
    try:
        if not isinstance(event, dict) or event.get('network') != 'tron-mainnet' or event.get('currency') != 'TRX':
            raise CommerceRejected('Unsupported asset or network')
        if purchase.network != 'tron-mainnet':
            raise CommerceRejected('Not a TRON native order')
        if not purchase.created_at or not purchase.expires_at:
            raise CommerceRejected('Unanchored invoice time')
        issued_ms = int(purchase.created_at.timestamp() * 1000)
        expires_ms = int(purchase.expires_at.timestamp() * 1000)
        expected = ExpectedTransfer(
            txid=event['txid'],
            address=purchase.destination.address,
            amount_sun=purchase.amount_sun,
            issued_ms=issued_ms,
            expires_ms=expires_ms,
        )
        expected.validate()  # validates genuine TRON Base58Check address
        key = getattr(settings, 'MOJ_COMMERCE_TRONGRID_API_KEY', '')
        if not isinstance(key, str):
            raise CommerceUnavailable('Invalid read-only TRON API configuration')
        # fetch() must be a trusted backend adapter. Never take RPC URLs from an event.
        try:
            body, receipt = fetch(expected.txid, api_key=key)
        except (CheckoutError, OSError, TimeoutError, ConnectionError) as exc:
            raise CommerceUnavailable('Approved TRON read source is unavailable') from exc
        proof = verify_finalized_trx(body, receipt, expected)
        # Verify every economic and temporal field, including server-derived
        # finalized block timestamp, against the signed merchant event.
        if (type(event.get('block_number')) is not int or
            type(event.get('paid_ms')) is not int or
            proof.block_number != event['block_number'] or
            proof.block_ms != event['paid_ms']):
            raise CommerceRejected('Fulfillment event disagrees with finalized chain block')
        return {
            'confirmed': True,
            'destination': proof.recipient,
            'amount_sun': proof.amount_sun,
            'txid': proof.txid,
            'network': 'tron-mainnet',
            'block_number': proof.block_number,
        }
    except CommerceRejected:
        raise
    except CommerceUnavailable:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        # Invalid chain proof / malformed merchant order must never authorize goods.
        raise CommerceRejected('Finalized transaction proof is invalid') from exc
    except (OSError, TimeoutError, ConnectionError) as exc:
        raise CommerceUnavailable('Approved TRON read source is unreachable') from exc
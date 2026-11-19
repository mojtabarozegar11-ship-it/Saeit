"""Read-only TRON mainnet verification; no signing or broadcast methods."""
import hashlib
import json
import re
import requests
from django.core.exceptions import ValidationError
from .simulation_invoice_contract import valid_tron_recipient, BASE58
from .models import PropPlan1Invoice
from .simulation_settlement import settle_and_provision

BASE_URL = "https://api.trongrid.io"

def recipient_hex(address):
    if not valid_tron_recipient(address):
        raise ValidationError("Invalid recipient")
    n = 0
    for char in address:
        n = n * 58 + BASE58.index(char)
    return n.to_bytes(25, "big")[:-4].hex()

def read_solidified_transaction(tx_hash):
    if not isinstance(tx_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", tx_hash):
        raise ValidationError("Invalid transaction ID")
    try:
        response = requests.post(BASE_URL + "/walletsolidity/gettransactionbyid",
                                 json={"value": tx_hash, "visible": False},
                                 timeout=(5, 10), allow_redirects=False)
        if response.status_code != 200:
            raise ValidationError("Verification temporarily unavailable")
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValidationError("Verification temporarily unavailable") from exc

def verify_invoice_transaction(invoice, tx_hash, body):
    try:
        raw = body["raw_data"]
        contracts = raw["contract"]
        results = body["ret"]
        if body["txID"] != tx_hash or len(contracts) != 1 or len(results) != 1:
            raise ValueError()
        if hashlib.sha256(bytes.fromhex(body["raw_data_hex"])).hexdigest() != tx_hash:
            raise ValueError()
        if results[0]["contractRet"] != "SUCCESS" or contracts[0]["type"] != "TransferContract":
            raise ValueError()
        value = contracts[0]["parameter"]["value"]
        if (value["to_address"].lower() != recipient_hex(invoice.recipient)
                or type(value["amount"]) is not int or value["amount"] != invoice.amount_sun
                or bytes.fromhex(raw["data"]).decode("ascii") != invoice.order_ref
                or type(raw["timestamp"]) is not int
                or raw["timestamp"] < int(invoice.created_at.timestamp() * 1000)):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Transaction does not match invoice or is not solidified") from exc
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def reconcile_simulation_invoice(*, invoice_id, owner, tx_hash, verified_owner_email):
    # Caller must supply verified identity from an authenticated server-side service.
    invoice = PropPlan1Invoice.objects.get(pk=invoice_id)
    if not owner.is_authenticated or not owner.is_active or owner.email != invoice.buyer_email or verified_owner_email != owner.email:
        raise ValidationError("Verified owner required")
    body = read_solidified_transaction(tx_hash)
    evidence = verify_invoice_transaction(invoice, tx_hash, body)
    return settle_and_provision(invoice_id=invoice_id, owner=owner, tx_hash=tx_hash,
        observed_network="tron-mainnet", observed_asset="TRX", observed_recipient=invoice.recipient,
        observed_amount_sun=invoice.amount_sun, independently_finalized=True,
        evidence_digest=evidence, verified_owner_email=verified_owner_email)

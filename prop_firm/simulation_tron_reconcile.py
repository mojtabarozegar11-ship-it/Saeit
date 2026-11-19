"""Read-only TRON mainnet verification; no signing or broadcast methods."""
import hashlib
import json
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirect refused", headers, fp)
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
        request = Request(BASE_URL + "/walletsolidity/gettransactionbyid",
                          data=json.dumps({"value": tx_hash, "visible": False}).encode("utf-8"),
                          headers={"Content-Type": "application/json", "Accept": "application/json"},
                          method="POST")
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            payload = response.read(262145)
            if response.status != 200 or len(payload) > 262144:
                raise ValidationError("Verification temporarily unavailable")
            return json.loads(payload)
    except (URLError, OSError, ValueError) as exc:
        raise ValidationError("Verification temporarily unavailable") from exc


def _varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError("Truncated varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            if value >= 1 << 64 or (shift and byte == 0):
                raise ValueError("Noncanonical varint")
            return value, pos
    raise ValueError("Oversized varint")


def _fields(data):
    """Strict protobuf subset for native TRON TransferContract evidence."""
    if not isinstance(data, bytes) or len(data) > 262144:
        raise ValueError("Invalid wire data")
    fields = {}
    pos = 0
    while pos < len(data):
        tag, pos = _varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if not 0 < number < 1 << 29 or number in fields:
            raise ValueError("Invalid or repeated wire field")
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire == 2:
            length, pos = _varint(data, pos)
            if length > len(data) - pos:
                raise ValueError("Truncated wire field")
            value = data[pos:pos + length]
            pos += length
        else:
            raise ValueError("Unsupported wire type")
        fields[number] = (wire, value)
    return fields


def _field(fields, number, wire):
    actual, value = fields[number]
    if actual != wire:
        raise ValueError("Incorrect wire type")
    return value


def _native_transfer(raw_bytes):
    # TRON protocol/core/Tron.proto: raw.data=10, contract=11,
    # timestamp=14; Contract.type=1, parameter=2; Any.value=2.
    raw = _fields(raw_bytes)
    contract = _fields(_field(raw, 11, 2))
    if _field(contract, 1, 0) != 1:
        raise ValueError("Not native TransferContract")
    any_body = _fields(_field(contract, 2, 2))
    if _field(any_body, 1, 2) != b"type.googleapis.com/protocol.TransferContract":
        raise ValueError("Incorrect contract parameter type")
    transfer = _fields(_field(any_body, 2, 2))
    if set(transfer) != {1, 2, 3}:
        raise ValueError("Unexpected native transfer fields")
    owner = _field(transfer, 1, 2)
    recipient = _field(transfer, 2, 2)
    amount = _field(transfer, 3, 0)
    timestamp = _field(raw, 14, 0)
    if any(len(address) != 21 or address[0] != 0x41 for address in (owner, recipient)):
        raise ValueError("Invalid mainnet address bytes")
    if not 0 < amount < 1 << 63 or not 0 < timestamp < 1 << 63:
        raise ValueError("Invalid signed int64")
    return owner.hex(), recipient.hex(), amount, _field(raw, 10, 2), timestamp


def verify_invoice_transaction(invoice, tx_hash, body):
    try:
        raw = body["raw_data"]
        contracts = raw["contract"]
        results = body["ret"]
        if body["txID"] != tx_hash or len(contracts) != 1 or len(results) != 1:
            raise ValueError()
        raw_bytes = bytes.fromhex(body["raw_data_hex"])
        if hashlib.sha256(raw_bytes).hexdigest() != tx_hash:
            raise ValueError()
        signed_owner, signed_recipient, signed_amount, signed_memo, signed_timestamp = _native_transfer(raw_bytes)
        if results[0]["contractRet"] != "SUCCESS" or contracts[0]["type"] != "TransferContract":
            raise ValueError()
        value = contracts[0]["parameter"]["value"]
        if (value["owner_address"].lower() != signed_owner
                or value["to_address"].lower() != signed_recipient
                or type(value["amount"]) is not int or value["amount"] != signed_amount
                or bytes.fromhex(raw["data"]) != signed_memo
                or type(raw["timestamp"]) is not int or raw["timestamp"] != signed_timestamp
                or signed_recipient != recipient_hex(invoice.recipient)
                or type(value["amount"]) is not int or value["amount"] != invoice.amount_sun
                or bytes.fromhex(raw["data"]).decode("ascii") != invoice.order_ref
                or type(raw["timestamp"]) is not int
                or raw["timestamp"] < int(invoice.created_at.timestamp() * 1000)):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Transaction does not match invoice or is not solidified") from exc
    evidence = {"schema": "mojprop-tron-native-v1", "network": "tron-mainnet",
                "txid": tx_hash, "owner": signed_owner, "recipient": signed_recipient,
                "amount_sun": signed_amount, "memo_hex": signed_memo.hex(),
                "timestamp_ms": signed_timestamp, "result": "SUCCESS"}
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

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

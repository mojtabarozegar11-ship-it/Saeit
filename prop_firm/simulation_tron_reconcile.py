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

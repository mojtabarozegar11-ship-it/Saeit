"""TRON SolidityNode dual-proof parser, read-only and fail-closed.

Only accepts direct native TRX TransferContract; rejects smart contracts, TRC20,
multi-contract transactions, unsolidified bodies, missing/failed execution and
inconsistent transaction IDs. Transport credentials/endpoints never go to users.

A second HTTP URL alone is not operator independence: activate only with TWO
approved separately managed providers. This module never broadcasts payments.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from services.mpw_trx_walletless_core import (
    PaymentHold, SolidifiedTransfer, NETWORK, TX_ID,
)

_ALPHABET="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_HEX_ADDR=re.compile(r"^41[0-9a-fA-F]{40}$")
_VALID_HOST=re.compile(r"^[a-z0-9][a-z0-9.-]{2,250}$")
_MAX_RESPONSE=150_000


def hex_to_tron_address(value: str) -> str:
    """Base58Check conversion for canonical TRON 0x41-prefixed addresses."""
    if not isinstance(value,str) or not _HEX_ADDR.fullmatch(value):
        raise PaymentHold("Malformed native TRON address")
    address=bytes.fromhex(value)
    checksum=hashlib.sha256(hashlib.sha256(address).digest()).digest()[:4]
    raw=address+checksum
    n=int.from_bytes(raw,"big")
    digits=""
    while n:
        n,rem=divmod(n,58)
        digits=_ALPHABET[rem]+digits
    return ("1" * (len(raw)-len(raw.lstrip(b"\0"))))+digits


def parse_solidified_native_trx(
    txid: str, body: dict, info: dict, *, source_id: str, network: str = NETWORK,
) -> SolidifiedTransfer:
    """Parse transaction body AND solidity receipt returned by same pinned provider."""
    # An explicitly tagged Shasta observation can be audited but must NEVER
    # masquerade as a payment accepted by the mainnet settlement kernel.
    if network not in (NETWORK, "tron-shasta"):
        raise PaymentHold("Unsupported TRON proof network")
    if not isinstance(txid,str) or not TX_ID.fullmatch(txid):
        raise PaymentHold("Malformed requested TRON transaction ID")
    if not source_id or not isinstance(body,dict) or not isinstance(info,dict):
        raise PaymentHold("Missing pinned provider or solidity response")
    if body.get("Error") or info.get("Error"):
        raise PaymentHold("RPC returned an application error")
    if body.get("txID") != txid or info.get("id") != txid:
        raise PaymentHold("Solidity transaction/receipt identity mismatch")
    contracts=body.get("raw_data",{}).get("contract")
    if not isinstance(contracts,list) or len(contracts)!=1:
        raise PaymentHold("Only one native TRX TransferContract is accepted")
    contract=contracts[0]
    if not isinstance(contract,dict) or contract.get("type")!="TransferContract":
        raise PaymentHold("TRC20, TRC10 and contract calls are not a native TRX transfer")
    parameter=contract.get("parameter")
    if not isinstance(parameter,dict) or not isinstance(parameter.get("value"),dict):
        raise PaymentHold("Missing native transfer contract parameters")
    transfer=parameter["value"]
    amount=transfer.get("amount")
    if type(amount) is not int or amount<=0:
        raise PaymentHold("Non-integer or zero native SUN transfer")
    sender=hex_to_tron_address(transfer.get("owner_address"))
    recipient=hex_to_tron_address(transfer.get("to_address"))
    ret=body.get("ret")
    if (not isinstance(ret,list) or len(ret)!=1 or not isinstance(ret[0],dict)
        or ret[0].get("contractRet")!="SUCCESS"):
        raise PaymentHold("TRX transaction execution is not successful")
    if info.get("result")=="FAILED":
        raise PaymentHold("Failed solidified execution")
    receipt=info.get("receipt")
    if not isinstance(receipt,dict) or receipt.get("result") not in (None,"SUCCESS"):
        raise PaymentHold("Failed or missing solidity execution receipt")
    block=info.get("blockNumber")
    ts_ms=info.get("blockTimeStamp")
    if type(block) is not int or block<=0 or type(ts_ms) is not int or ts_ms<=0:
        raise PaymentHold("Missing solidified block metadata")
    raw_ts=body.get("raw_data",{}).get("timestamp")
    if type(raw_ts) is not int or raw_ts<=0 or raw_ts>ts_ms+60_000:
        raise PaymentHold("Malformed on-chain transaction timestamp")
    timestamp=datetime.fromtimestamp(ts_ms/1000,timezone.utc)
    return SolidifiedTransfer(
        source_id=source_id,tx_hash=txid,network=network,
        recipient=recipient,sender=sender,amount_sun=amount,
        block_time=timestamp,solidified=True,transfer_contract=True,
        execution_success=True,
    )


@dataclass(frozen=True)
class RpcProvider:
    """Reviewed provider metadata is server-owned. Never deserialize from buyer input."""
    source_id: str
    operator_id: str
    endpoint: str
    api_key: str = ""
    api_key_header: str = "TRON-PRO-API-KEY"

    def validate(self):
        if not self.source_id or not self.operator_id:
            raise PaymentHold("Missing audited RPC provider identity")
        parsed=urllib.parse.urlsplit(self.endpoint)
        hostname=(parsed.hostname or "").lower()
        if (parsed.scheme!="https" or parsed.username or parsed.password or parsed.port not in (None,443)
            or parsed.path not in ("","/") or parsed.query or parsed.fragment or not _VALID_HOST.fullmatch(hostname)
            or ".." in hostname or not hostname.endswith((".com",".io",".net",".org",".cloud",".dev"))):
            raise PaymentHold("RPC HTTPS origin is not an allowed public host")
        try:
            addr=ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise PaymentHold("IP-literal RPC hosts forbidden")
        # This class powers MAINNET settlement only. Shasta/Nile RPC providers
        # must never be accepted here even if configured with two operator IDs.
        if (hostname in ("api.shasta.trongrid.io", "api.nileex.io", "nile.trongrid.io")
            or re.search(r"(^|[.-])(shasta|nile|testnet)([.-]|$)", hostname)):
            raise PaymentHold("Testnet provider cannot validate mainnet payments")
        if type(self.api_key) is not str or len(self.api_key)>512:
            raise PaymentHold("Untrusted RPC authentication material")
        if self.api_key_header not in ("TRON-PRO-API-KEY", "X-API-KEY"):
            raise PaymentHold("Unsupported RPC authentication header")
        # TronGrid and Nodit use different credential headers. Their production
        # gateways must never be probed with a hardcoded demo credential.
        if hostname == "api.trongrid.io" and (not self.api_key or self.api_key_header != "TRON-PRO-API-KEY"):
            raise PaymentHold("Authenticated TronGrid configuration required")
        if hostname == "tron-mainnet.nodit.io" and (not self.api_key or self.api_key_header != "X-API-KEY"):
            raise PaymentHold("Authenticated Nodit configuration required")

    def request_headers(self) -> dict[str,str]:
        self.validate()
        headers={"Content-Type":"application/json","Accept":"application/json"}
        if self.api_key:
            headers[self.api_key_header]=self.api_key
        return headers


def verify_distinct_provider_config(first: RpcProvider, second: RpcProvider) -> None:
    if not isinstance(first,RpcProvider) or not isinstance(second,RpcProvider):
        raise PaymentHold("Two reviewed providers required")
    first.validate()
    second.validate()
    a=urllib.parse.urlsplit(first.endpoint).hostname.lower()
    b=urllib.parse.urlsplit(second.endpoint).hostname.lower()
    if first.source_id==second.source_id or first.operator_id==second.operator_id or a==b:
        raise PaymentHold("Not independent RPC operators and endpoints")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise PaymentHold("RPC must not redirect")


def _post(provider: RpcProvider, path: str, txid: str,
          transport:Callable|None=None) -> dict:
    if path not in ("/walletsolidity/gettransactionbyid",
                    "/walletsolidity/gettransactioninfobyid",
                    "/walletsolidity/getnowblock"):
        raise PaymentHold("Only read-only solidity methods allowed")
    if transport is not None:
        response=transport(provider,path,txid)
    else:
        url=provider.endpoint.rstrip("/")+path
        head_request=path.endswith("getnowblock")
        params={"value":txid,"visible":False}
        payload=None if head_request else json.dumps(params,separators=(",",":")).encode("utf8")
        headers=provider.request_headers()
        # SolidityNode's GetNowBlock uses GET (including Nodit and TRON's
        # official reference). Transaction body/receipt methods use POST.
        request=urllib.request.Request(url,data=payload,headers=headers,
                                       method="GET" if head_request else "POST")
        opener=urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(request,timeout=8) as resp:
                if resp.status!=200 or resp.headers.get("Content-Type","").split(";")[0]!="application/json":
                    raise PaymentHold("RPC returned an invalid HTTP response")
                raw=resp.read(_MAX_RESPONSE+1)
                if len(raw)>_MAX_RESPONSE:
                    raise PaymentHold("Oversized TRON RPC response")
        except (TimeoutError,urllib.error.URLError,socket.timeout,OSError) as exc:
            raise PaymentHold("TRON RPC unavailable") from exc
        try:response=json.loads(raw)
        except (ValueError,UnicodeDecodeError) as exc:raise PaymentHold("RPC JSON decode failed") from exc
    if not isinstance(response,dict) or response.get("Error"):
        raise PaymentHold("Untrusted solidity response")
    return response


def query_solidified_transfer(provider:RpcProvider,txid:str,*,transport:Callable|None=None):
    """Get native TRX body and corresponding solidified info from one RPC provider."""
    provider.validate()
    if not isinstance(txid,str) or not TX_ID.fullmatch(txid):
        raise PaymentHold("Untrusted transaction hash")
    body=_post(provider,"/walletsolidity/gettransactionbyid",txid,transport)
    info=_post(provider,"/walletsolidity/gettransactioninfobyid",txid,transport)
    return parse_solidified_native_trx(txid,body,info,source_id=provider.source_id)


def query_solidified_head(provider:RpcProvider,*,transport:Callable|None=None,
                          now:datetime|None=None) -> int:
    """Read the newest solidified block without inspecting merchant payments.

    A healthy head is necessary, but is never sufficient, for live settlement.
    """
    provider.validate()
    observation=now or datetime.now(timezone.utc)
    if observation.tzinfo is None or observation.utcoffset() is None:
        raise PaymentHold("Untrusted observation time")
    result=_post(provider,"/walletsolidity/getnowblock","",transport)
    raw=result.get("block_header",{}).get("raw_data",{})
    height=raw.get("number")
    millis=raw.get("timestamp")
    if type(height) is not int or height<=0 or type(millis) is not int or millis<=0:
        raise PaymentHold("Invalid solidified head")
    try:
        block_time=datetime.fromtimestamp(millis/1000,timezone.utc)
    except (OverflowError,ValueError,OSError) as exc:
        raise PaymentHold("Invalid solidity head timestamp") from exc
    age=(observation.astimezone(timezone.utc)-block_time).total_seconds()
    if age < -60 or age > 600:
        raise PaymentHold("Stale or future TRON solidity head")
    return height


def verified_live_pair(first:RpcProvider,second:RpcProvider,*,trusted_operator_attestation:bool,
                      transport:Callable|None=None):
    """Return TrustedNodePair only with explicit external operator review."""
    verify_distinct_provider_config(first,second)
    if trusted_operator_attestation is not True:
        raise PaymentHold("Independence review has not been attested")
    from services.mpw_walletless_django_test_bridge import TrustedNodePair
    return TrustedNodePair(
        identifier_a=first.source_id,identifier_b=second.source_id,
        prove_a=lambda tx:query_solidified_transfer(first,tx,transport=transport),
        prove_b=lambda tx:query_solidified_transfer(second,tx,transport=transport),
        audited_as_independent=True,
    )

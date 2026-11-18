#!/usr/bin/env python3
"""One live public blockchain API shape check; no secrets or transfer signing.

Never logs wallet balance, transaction identifiers, payer addresses or history.
Retries are deliberately omitted: no API charge or burst requests.
"""
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
import json

RECEIVER="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
ROOT="https://api.trongrid.io"
qs=urlencode({
    "only_to":"true",
    "only_confirmed":"true",
    "limit":"1",
})
u=f"{ROOT}/v1/accounts/{RECEIVER}/transactions?{qs}"
record={
    "schema":"mojprop.trongrid.live.readonly.v1",
    "method":"GET",
    "tls_expected":True,
    "broadcast_called":False,
    "credentials_used":False,
    "transactions_logged":False,
    "merchant_wallet_derived_from_pinned_owner_source":True,
    "http_status":None,
    "indexer_shape_verified":False,
    "index_data_list":False,
    "metadata_available":False,
    "possible_api_key_or_ratelimit_required":False,
}
try:
    req=Request(u,method="GET",headers={"Accept":"application/json"})
    with urlopen(req,timeout=14) as r:
        record["http_status"]=r.status
        if r.geturl()!=u:
            raise ValueError("Unexpected redirect")
        raw=r.read(150001)
    if len(raw)>150000:
        raise ValueError("Indexer reply too large")
    j=json.loads(raw.decode("utf8"))
    record["index_data_list"]=type(j.get("data")) is list
    record["metadata_available"]=type(j.get("meta")) is dict
    record["indexer_shape_verified"]=bool(
        j.get("success") is True and record["index_data_list"]
        and record["metadata_available"])
except HTTPError as e:
    record["http_status"]=e.code
    record["possible_api_key_or_ratelimit_required"]=e.code in (401,403,429)
    record["error_kind"]="HTTPError"
except (URLError,ValueError,OSError,TimeoutError,UnicodeError) as e:
    record["error_kind"]=type(e).__name__
print("MOJPROP_TRONGRID_READONLY_PROBE="+json.dumps(record,sort_keys=True))
if not record["indexer_shape_verified"]:
    raise SystemExit(1)

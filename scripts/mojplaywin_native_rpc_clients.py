"""Server-pinned read-only ETH/TRX RPC clients for staged automatic settlement.

Accepts only server-defined methods and chain hosts. No keys, signatures,
transaction broadcasting, wallet changes or client-supplied RPC URLs.
"""
import json
import re
from urllib.request import Request, urlopen

ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"
TRX_RPC_URL = "https://tron-rpc.publicnode.com"
ETH_METHODS = frozenset({
    "eth_chainId","eth_blockNumber","eth_getTransactionByHash",
    "eth_getTransactionReceipt","eth_getBlockByNumber",
})
TRX_PATHS = frozenset({
    "/walletsolidity/gettransactionbyid",
    "/walletsolidity/gettransactioninfobyid",
})
MAX_RPC_BYTES = 250_000


class NativeRpcUnavailable(ValueError):
    pass


def _http_json(url, document, *, opener=urlopen):
    request=Request(
        url,
        data=json.dumps(document, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type":"application/json","Accept":"application/json",
                 "User-Agent":"MojPlayWin-ReadOnly-RPC/1"},
        method="POST",
    )
    try:
        with opener(request,timeout=18) as response:
            data=response.read(MAX_RPC_BYTES+1)
        if len(data)>MAX_RPC_BYTES:
            raise NativeRpcUnavailable("RPC response too large")
        result=json.loads(data.decode("utf-8"))
        if not isinstance(result,dict):
            raise NativeRpcUnavailable("RPC response not an object")
        if result.get("error") or result.get("Error"):
            raise NativeRpcUnavailable("RPC returned failure")
        return result
    except (OSError,TimeoutError,UnicodeError,ValueError) as exc:
        raise NativeRpcUnavailable("RPC failed safe bounded response checks") from exc


def ethereum_rpc(method,params):
    if method not in ETH_METHODS or not isinstance(params,list) or len(params)>2:
        raise NativeRpcUnavailable("Disallowed Ethereum RPC method")
    if method in ("eth_getTransactionByHash","eth_getTransactionReceipt"):
        if len(params)!=1 or not isinstance(params[0],str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",params[0]):
            raise NativeRpcUnavailable("Invalid Ethereum receipt request")
    if method=="eth_getBlockByNumber":
        if len(params)!=2 or params[1] is not False:
            raise NativeRpcUnavailable("Only block headers can be queried")
        if not isinstance(params[0],str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}",params[0]):
            raise NativeRpcUnavailable("Bad block height")
    if method in ("eth_chainId","eth_blockNumber") and params:
        raise NativeRpcUnavailable("Unexpected Ethereum RPC params")
    body={"jsonrpc":"2.0","id":1,"method":method,"params":params}
    result=_http_json(ETH_RPC_URL,body)
    if result.get("jsonrpc")!="2.0" or result.get("id")!=1 or "result" not in result:
        raise NativeRpcUnavailable("Malformed Ethereum RPC response")
    return result["result"]


def tron_solidity_rpc(path,request):
    if path not in TRX_PATHS:
        raise NativeRpcUnavailable("Disallowed TRON RPC method")
    if not isinstance(request,dict) or set(request)!={"value"}:
        raise NativeRpcUnavailable("Invalid TRON RPC request")
    txid=request["value"]
    if not isinstance(txid,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",txid):
        raise NativeRpcUnavailable("Invalid TRON tx ID")
    data=_http_json(TRX_RPC_URL+path,{"value":txid})
    # Empty responses are possible for pending or unknown transactions;
    # the independent verifier rejects both. Never mark them paid here.
    return data

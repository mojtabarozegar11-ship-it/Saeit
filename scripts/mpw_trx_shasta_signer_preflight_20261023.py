#!/usr/bin/env python3
"""VPS-only Shasta test signer preflight. Secret never leaves the VPS."""
from __future__ import annotations
import json,os,stat,subprocess,urllib.request
from pathlib import Path

HOME=Path("/home/githubops")
BASE=HOME/".local/share/moj1-shasta-test-20261021"
KEY=BASE/"wallet.key"
META=BASE/"wallet-public.json"
NODE=BASE/"moj1-node"
APP=BASE/"runtime-governance/moj1-pilot"
EXPECTED="TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"

def preflight():
    if os.geteuid()==0 or BASE.is_symlink() or KEY.is_symlink():
        raise RuntimeError("Unsafe VPS Shasta account access")
    if not KEY.is_file() or stat.S_IMODE(KEY.stat().st_mode)!=0o600 or KEY.stat().st_size!=32:
        raise RuntimeError("Protected Shasta signer is not usable")
    public=json.loads(META.read_text("utf8"))
    if public.get("network")!="SHASTA_TEST_ONLY" or public.get("production_approved") is not False:
        raise RuntimeError("Unexpected wallet deployment network guard")
    if not NODE.is_file() or not APP.is_dir() or not (APP/"node_modules/tronweb").is_dir():
        raise RuntimeError("Previously prepared test signer runtime missing")
    task=subprocess.run([str(NODE),"-e","require('tronweb')"],cwd=str(APP),
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            timeout=20)
    if task.returncode!=0:
        raise RuntimeError("TronWeb 6 runtime not importable")
    req=urllib.request.Request("https://api.shasta.trongrid.io/wallet/getaccount",
            data=json.dumps({"address":EXPECTED,"visible":True}).encode("utf8"),
            headers={"Accept":"application/json","Content-Type":"application/json",
                     "User-Agent":"MojPlayWin-Shasta-Canary/1.0"},method="POST")
    with urllib.request.urlopen(req,timeout=15) as res:
        raw=res.read(100_001)
    if len(raw)>100_000:
        raise RuntimeError("Shasta account response oversized")
    info=json.loads(raw)
    if info.get("address")!=EXPECTED or type(info.get("balance")) is not int:
        raise RuntimeError("Shasta test wallet inactive")
    available=info["balance"]
    if available<20_000_000:
        raise RuntimeError("Insufficient Shasta test TRX")
    return {"status":"SHASTA_PRIVATE_SIGNER_READY",
            "testnet":"tron-shasta","private_key_exported":False,
            "can_broadcast_test_transaction":True,
            "current_test_trx":f"{available/1_000_000:.6f}",
            "merchant_mainnet_used":False}

if __name__=="__main__":
    try:
        print("MPW_SHASTA_SIGNER_PREFLIGHT="+json.dumps(preflight(),sort_keys=True))
    except Exception as exc:
        print("MPW_SHASTA_SIGNER_PREFLIGHT="+json.dumps({
            "status":"BLOCKED","reason_type":type(exc).__name__,
            "reason":str(exc) if isinstance(exc,RuntimeError) else "private_preflight_failed",
            "private_key_exported":False},sort_keys=True))
        raise SystemExit(2)

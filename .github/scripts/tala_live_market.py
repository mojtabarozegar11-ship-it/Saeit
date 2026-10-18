#!/usr/bin/env python3
"""Collect verifiable international spot, FX reference and crypto quotes for Tala.

Only predefined HTTPS providers are contacted. Never fabricates rates or
substitutes reference USD/IRR for Iran's domestic open-market quotation.
The generated public snapshot has no secrets, credentials or financial records.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import sys
import urllib.request

OZ_TO_GRAM = 31.1034768
SPOTS = {"xau": "XAU", "xag": "XAG", "xpt": "XPT", "xpd": "XPD"}
COINS = {"btc": "bitcoin", "eth": "ethereum", "usdt": "tether",
         "trx": "tron", "bnb": "binancecoin", "sol": "solana"}
FX = ("USD", "EUR", "GBP", "AED", "TRY", "CAD", "IRR")
PROVIDERS = ("api.gold-api.com", "api.coingecko.com", "open.er-api.com")

def utc(ts):
    if isinstance(ts,(int,float)):
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat().replace("+00:00","Z")
    if not isinstance(ts,str):
        raise ValueError("invalid observed time")
    parsed=dt.datetime.fromisoformat(ts.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must contain timezone")
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")

def reasonable(value,lower=0,max_value=1e10):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return False
    return math.isfinite(value) and lower < value < max_value

def get(url):
    if not url.startswith("https://") or not any(url.split("/")[2]==h for h in PROVIDERS):
        raise RuntimeError("TALA_UNTRUSTED_PROVIDER")
    req=urllib.request.Request(url,headers={"User-Agent":"ZomorodTalaPublicPrices/1.0 (https://zomorodmelal.ir/tala/)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=11) as response:
        if response.status!=200 or "json" not in response.headers.get("Content-Type",""):
            raise ValueError("unexpected response")
        raw=response.read(200001)
        if len(raw)>200000:
            raise ValueError("provider response too big")
        return json.loads(raw)

def record(symbol,price,currency,unit,source,source_url,observed,kind,now):
    if not reasonable(price):
        raise ValueError("invalid market rate")
    observed_iso=utc(observed)
    age=(now-dt.datetime.fromisoformat(observed_iso.replace("Z","+00:00"))).total_seconds()
    if age < -300 or age > 604800:  # Reject future/very old source observations.
        raise ValueError("source observation outside bounded window")
    return {"symbol":symbol,"price":round(price,8),"currency":currency,"unit":unit,
            "source":source,"source_url":source_url,"observed_at":observed_iso,"group":kind}

def assemble(fetch=get,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    quotes={}
    failures=[]
    for symbol,remote in SPOTS.items():
        try:
            data=fetch("https://api.gold-api.com/price/"+remote)
            if data.get("symbol")!=remote or data.get("currency")!="USD":
                raise ValueError("spot symbol or currency mismatch")
            price=float(data["price"])
            quotes[symbol]=record(symbol,price/OZ_TO_GRAM,"USD","gram",
                "Gold API","https://gold-api.com/",data["updatedAt"],"metals",now)
        except (ValueError,KeyError,TypeError,TimeoutError,OSError) as e:
            failures.append(symbol+":"+type(e).__name__)
    coin_ids=",".join(COINS.values())
    try:
        data=fetch("https://api.coingecko.com/api/v3/simple/price?ids="+coin_ids+"&vs_currencies=usd&include_last_updated_at=true")
        for symbol,remote in COINS.items():
            try:
                row=data[remote]
                quotes[symbol]=record(symbol,row["usd"],"USD","coin",
                    "CoinGecko","https://www.coingecko.com/",row["last_updated_at"],"crypto",now)
            except (ValueError,KeyError,TypeError,OverflowError,OSError) as e:
                failures.append(symbol+":"+type(e).__name__)
    except (ValueError,KeyError,TypeError,TimeoutError,OSError) as e:
        failures.append("coingecko:"+type(e).__name__)
    try:
        data=fetch("https://open.er-api.com/v6/latest/USD")
        if data.get("result")!="success" or data.get("base_code")!="USD":
            raise ValueError("unsupported forex reference")
        observed=data["time_last_update_unix"]
        rates=data["rates"]
        for target in FX:
            try:
                price=rates[target]
                # Reference cross-rate of 1 USD, NOT free-market Iranian quotes.
                quotes["usd_"+target.lower()]=record("usd_"+target.lower(),price,target,"per_usd",
                    "ExchangeRate-API reference","https://www.exchangerate-api.com/",
                    observed,"forex_reference",now)
            except (ValueError,KeyError,TypeError,OverflowError,OSError) as e:
                failures.append("usd_"+target.lower()+":"+type(e).__name__)
    except (ValueError,KeyError,TypeError,TimeoutError,OSError) as e:
        failures.append("fx:"+type(e).__name__)
    if not quotes:
        raise RuntimeError("TALA_ALL_PROVIDERS_UNAVAILABLE")
    return {"scope":"tala","schema":1,"market":"international_reference",
            "generated_at":utc(now.isoformat()),"quotes":quotes,
            "providers":sorted(set(x["source"] for x in quotes.values())),
            "partial":bool(failures),"failed_symbols":failures}

def check_doc(doc):
    if doc.get("scope")!="tala" or doc.get("schema")!=1 or doc.get("market")!="international_reference":
        raise ValueError("scope/schema mismatch")
    if not isinstance(doc.get("quotes"),dict) or len(doc["quotes"])<1 or len(doc["quotes"])>24:
        raise ValueError("invalid quote collection")
    for name,value in doc["quotes"].items():
        if name not in set(SPOTS)|set(COINS)|{"usd_"+x.lower() for x in FX}:
            raise ValueError("unapproved symbol")
        if not reasonable(value["price"]) or value.get("symbol")!=name:
            raise ValueError("invalid quote")
        if value.get("source") not in ("Gold API","CoinGecko","ExchangeRate-API reference"):
            raise ValueError("unapproved source")
        utc(value["observed_at"])
    utc(doc["generated_at"])

def selftest():
    now=dt.datetime(2026,10,18,5,0,tzinfo=dt.timezone.utc)
    def fake(url):
        if "/price/" in url:
            symbol=url.rsplit("/",1)[-1]
            return {"symbol":symbol,"currency":"USD","price":3110.34768,
                    "updatedAt":"2026-10-18T04:59:00Z"}
        if "coingecko" in url:
            return {coin:{"usd":100,"last_updated_at":1792299540} for coin in COINS.values()}
        return {"result":"success","base_code":"USD",
                "time_last_update_unix":1792281751,
                "rates":{k:2 for k in FX}}
    doc=assemble(fake,now)
    assert len(doc["quotes"])==17
    assert doc["quotes"]["xau"]["price"]==100
    assert doc["quotes"]["usd_irr"]["source"]=="ExchangeRate-API reference"
    check_doc(doc)
    print("TALA_LIVE_PROVIDER_SELFTEST=passed")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--output")
    args=parser.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.output:
        parser.error("--output required")
    doc=assemble()
    check_doc(doc)
    target=Path(args.output)
    if not target.parent.is_dir() or target.exists() or target.is_symlink():
        raise RuntimeError("TALA_UNSAFE_OUTPUT_PATH")
    with target.open("x",encoding="utf-8") as output:
        json.dump(doc,output,ensure_ascii=False,separators=(",",":"))
        output.write("\n")
    os.chmod(target,0o600)
    print("TALA_INTERNATIONAL_LIVE_QUOTES="+str(len(doc["quotes"])))
    print("TALA_FEED_PARTIAL="+str(doc["partial"]).lower())

if __name__=="__main__":
    main()

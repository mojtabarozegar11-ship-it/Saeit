"""Server-side HTTPS price and registered native TRX receiving wallet."""
import json
from decimal import Decimal
from urllib.request import Request,urlopen
from mpw_commerce.invoicing import RECEIVERS
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

def receive_wallet():
 chain,address,decimals=RECEIVERS.get("TRX",(None,None,None))
 if chain!="tron-mainnet" or decimals!=6 or not address:
  raise RuntimeError("TRX receiving wallet unavailable")
 tron_address_to_hex(address)
 return address

def price_usd():
 req=Request("https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd",headers={"Accept":"application/json","User-Agent":"MojPlayWinGuestTRX/1"},method="GET")
 with urlopen(req,timeout=9) as response:raw=response.read(2049)
 if len(raw)>2048:raise ValueError("Oversized price quote")
 value=json.loads(raw.decode("utf8")).get("tron",{}).get("usd")
 if type(value) not in (int,float,str):raise ValueError("Invalid TRX quote")
 d=Decimal(str(value))
 if not d.is_finite() or not Decimal("0.001")<=d<=Decimal("100"):raise ValueError("TRX quote outside safety range")
 return d

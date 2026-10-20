"""Atomic, unique Sun-amount invoice allocation; no customer accounts."""
import secrets,time,sqlite3
from decimal import Decimal,ROUND_CEILING
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
from .guest_database import connect
from .guest_pricing import receive_wallet,price_usd
from .guest_receipts import hash_secret,make_receipt

def issue(product, sender):
 tron_address_to_hex(sender)
 receiver=receive_wallet()
 rate=price_usd()
 usd=Decimal(product.price)
 base=int((usd*1000000/rate).to_integral_value(rounding=ROUND_CEILING))
 if base<1000000 or base>100000000000:raise ValueError("Unrepresentable TRX quote")
 now=int(time.time()*1000);secret=secrets.token_urlsafe(36)
 db=connect()
 try:
  db.execute("BEGIN IMMEDIATE")
  count=db.execute("SELECT count(*) FROM guest_orders WHERE status='pending' AND expires_ms>?",(now,)).fetchone()[0]
  if count>1400:raise RuntimeError("Checkout at capacity")
  for attempt in range(40):
   sun=base+secrets.randbelow(9900)+1
   try:
    cursor=db.execute("INSERT INTO guest_orders(claim_sha,product_id,usd,rate,amount_sun,sender,receiver,issued_ms,expires_ms) VALUES(?,?,?,?,?,?,?,?,?)",
     (hash_secret(secret),product.pk,str(usd),str(rate),sun,sender,receiver,now,now+600000))
    db.commit()
    return make_receipt(cursor.lastrowid,secret)
   except sqlite3.IntegrityError:continue
  raise RuntimeError("Unique quote not available")
 finally:db.close()

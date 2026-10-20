"""Unforgeable, time-limited guest receipt cookie."""
import hashlib,secrets
from django.core import signing
from .guest_database import connect
COOKIE="mpw_guest_trx_claim"
SALT="mpw-guest-20261020"
LIFETIME=14*86400

def hash_secret(value):
 return hashlib.sha256(value.encode()).hexdigest()
def make_receipt(order_id,secret):
 return signing.dumps({"id":order_id,"secret":secret},salt=SALT)
def get_order(cookie):
 if not cookie or len(cookie)>400:return None
 try:
  claim=signing.loads(cookie,salt=SALT,max_age=LIFETIME)
  if type(claim) is not dict or type(claim.get("id")) is not int or type(claim.get("secret")) is not str:return None
  db=connect()
  try:row=db.execute("SELECT * FROM guest_orders WHERE id=?",(claim["id"],)).fetchone()
  finally:db.close()
  if row and secrets.compare_digest(row["claim_sha"],hash_secret(claim["secret"])):return dict(row)
 except (signing.BadSignature,signing.SignatureExpired,ValueError,TypeError):
  return None
 return None

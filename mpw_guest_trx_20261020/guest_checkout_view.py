"""No-account TRX checkout handler for one MojPlayWin product."""
import time
from decimal import Decimal
from datetime import datetime,timezone
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from .guest_orders import issue
from .guest_receipts import COOKIE,LIFETIME,get_order
from .guest_settlement import confirm
from .guest_product import approved_item

@never_cache
@csrf_protect
@require_http_methods(["GET","POST"])
def checkout(request,product_id):
 if not request.is_secure() or request.get_host().split(":")[0].lower() not in ("mojplaywin.com","www.mojplaywin.com"):raise Http404
 product,_=approved_item(product_id)
 token=request.COOKIES.get(COOKIE)
 order=get_order(token)
 error=None
 if request.method=="POST":
  action=request.POST.get("action")
  if action=="start":
   try:
    token=issue(product,request.POST.get("sender","").strip())
    order=get_order(token)
   except Exception:
    error="A secure TRX quote could not be issued. Do not send any funds."
  elif action=="verify" and order and order["product_id"]==product_id:
   try:
    confirm(order,request.POST.get("txid","").strip())
    order=get_order(token)
   except Exception:
    error="Payment not confirmed. Check the sender, exact TRX amount and transaction ID; do not pay twice."
  else:error="Invalid guest checkout request."
 if order and order["product_id"]!=product_id:order=None
 expired=bool(order and int(time.time()*1000)>order["expires_ms"])
 expiry_utc=datetime.fromtimestamp(order["expires_ms"]/1000,timezone.utc).strftime("%Y-%m-%d %H:%M") if order else ""
 amount=format(Decimal(order["amount_sun"])/Decimal(1000000),".6f") if order else ""
 response=render(request,"mpw_commerce/guest_trx.html",{"product":product,"order":order,"amount":amount,"expired":expired,"expiry_utc":expiry_utc,"error":error})
 response["Cache-Control"]="private, no-store"
 if request.method=="POST" and action=="start" and order and not error:
  response.set_cookie(COOKIE,token,secure=True,httponly=True,samesite="Lax",path="/commerce/guest-trx/",max_age=LIFETIME)
 return response

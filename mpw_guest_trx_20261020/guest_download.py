"""Paid-only guest download, scoped to a signed receipt on the same browser."""
import os
from django.http import Http404,FileResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .guest_receipts import COOKIE,get_order
from .guest_product import approved_item

@never_cache
@require_GET
def download(request):
 if not request.is_secure() or request.get_host().split(":")[0].lower() not in ("mojplaywin.com","www.mojplaywin.com"):raise Http404
 order=get_order(request.COOKIES.get(COOKIE))
 if order is None or order["status"]!="paid" or not order["txid"]:raise Http404
 product,path=approved_item(order["product_id"])
 fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW)
 response=FileResponse(os.fdopen(fd,"rb"),as_attachment=True,filename=path.name)
 response["Cache-Control"]="no-store, private"
 response["X-Content-Type-Options"]="nosniff"
 response["Referrer-Policy"]="no-referrer"
 return response

"""MojPlayWin guest checkout feature; disabled until integrity checks pass."""
from django.http import Http404

def guest_trx_checkout(request, product_id):
    raise Http404

def guest_trx_download(request):
    raise Http404

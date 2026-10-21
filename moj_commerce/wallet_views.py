"""Seller-authenticated wallet proof endpoints, source-only and NOT live-mounted."""
import json
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .services import CommerceRejected
from .wallet_proof import issue_wallet_challenge, complete_wallet_challenge


def _answer(payload,status=200):
    out=JsonResponse(payload,status=status)
    out['Cache-Control']='no-store, private'
    out['Referrer-Policy']='no-referrer'
    out['X-Content-Type-Options']='nosniff'
    return out


def _seller(request):
    user=getattr(request,'user',None)
    if user is None or not user.is_authenticated or not user.is_active:
        raise Http404
    return user.pk


@csrf_protect
@require_POST
def create_wallet_challenge(request,merchant_id,address_id):
    owner=_seller(request)
    try:
        challenge=issue_wallet_challenge(merchant_id,address_id,owner)
    except CommerceRejected:
        return _answer({'error':'wallet_challenge_unavailable'},409)
    return _answer(challenge,status=201)


@csrf_protect
@require_POST
def verify_wallet_challenge(request,merchant_id,address_id):
    owner=_seller(request)
    if request.content_type!='application/json':
        return _answer({'error':'json_required'},415)
    if len(request.body)>1024:
        return _answer({'error':'payload_too_large'},413)
    try:
        def no_duplicates(pairs):
            result={}
            for key,value in pairs:
                if key in result: raise ValueError('duplicate key')
                result[key]=value
            return result
        payload=json.loads(request.body,object_pairs_hook=no_duplicates)
        if (not isinstance(payload,dict) or set(payload)!={'challenge_id','signature'} or
            not isinstance(payload['challenge_id'],str) or
            not isinstance(payload['signature'],str) or
            len(payload['challenge_id'])>40 or len(payload['signature'])>132):
            raise ValueError('invalid shape')
    except (ValueError,UnicodeError):
        return _answer({'error':'invalid_wallet_proof'},400)
    try:
        proof=complete_wallet_challenge(merchant_id,address_id,owner,
            payload['challenge_id'],payload['signature'])
    except CommerceRejected:
        return _answer({'error':'wallet_proof_rejected'},409)
    return _answer(proof)
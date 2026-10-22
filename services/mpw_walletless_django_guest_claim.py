"""No-registration guest claims bound to a unique Django buyer — TEST MariaDB ONLY.

A guest buyer sees no signup form. Server creates one unique user with an
unusable password, stores only a SHA256 digest of a 256-bit bearer claim, and
sets signed Secure/HttpOnly/SameSite cookie. No shared public buyer identity.
A lost cookie cannot grant purchase ownership; staff-assisted recovery needed.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_django_test_bridge import _test_only_guard

COOKIE_NAME="mpw_trx_easy_guest"
COOKIE_SALT="mpw.walletless.guest.claim.v1"
COOKIE_LIFETIME=30*86400
COOKIE_PATH="/commerce/trx-easy/"
CLAIM_MAX_LENGTH=512

def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _validate_env(django_settings,db):
    _test_only_guard(django_settings,db)
    if db.alias!="default":
        raise PaymentHold("Guest identity requires isolated default MariaDB test connection")

def _read_cookie(cookie: str, *, django_settings, db) -> int|None:
    from django.core import signing
    from django.contrib.auth import get_user_model
    _validate_env(django_settings,db)
    if not isinstance(cookie,str) or not 10<len(cookie)<=CLAIM_MAX_LENGTH:
        return None
    try:
        payload=signing.loads(cookie,salt=COOKIE_SALT,max_age=COOKIE_LIFETIME)
    except (signing.BadSignature,signing.SignatureExpired,TypeError,ValueError):
        return None
    if (type(payload) is not dict or type(payload.get("id")) is not int
        or payload["id"]<=0 or type(payload.get("secret")) is not str
        or len(payload["secret"])!=64
        or any(c not in "0123456789abcdef" for c in payload["secret"])):
        return None
    digest=hashlib.sha256(payload["secret"].encode("ascii")).hexdigest()
    with db.cursor() as cursor:
        cursor.execute(
          """SELECT buyer_id,secret_sha256 FROM mpw_walletless_trx_guest_claim_v1
             WHERE id=%s AND expires_at>UTC_TIMESTAMP(6) LIMIT 1""",
          [payload["id"]])
        row=cursor.fetchone()
    if not row or not hmac.compare_digest(str(row[1]),digest):
        return None
    user=get_user_model().objects.filter(pk=row[0],is_active=True).first()
    if not user:
        return None
    return int(row[0])


def read_guest_buyer(cookie:str,*,django_settings=None,db=None)->int|None:
    from django.conf import settings
    from django.db import connection
    return _read_cookie(cookie,django_settings=django_settings or settings,
                        db=db or connection)


def create_guest_buyer(*,django_settings=None,db=None):
    """Return (Django buyer id, signed bearer). Invoked only under CSRF-protected POST.

    Caller must enforce public ingress rate-limiting before creating a new
    guest. The adapter is entirely locked to a test_ schema.
    """
    from django.core import signing
    from django.db import transaction, connection
    from django.contrib.auth import get_user_model
    from django.conf import settings
    config=django_settings or settings
    conn=db or connection
    _validate_env(config,conn)
    with transaction.atomic(using=conn.alias):
        model=get_user_model()
        username="mpwguest_"+secrets.token_hex(18)
        ident=secrets.token_hex(32)
        attr=getattr(model,"USERNAME_FIELD","username")
        obj=model(**{attr:username})
        if not hasattr(obj,"set_unusable_password"):
            raise PaymentHold("Guest buyer model cannot prevent password sign-in")
        obj.set_unusable_password()
        if hasattr(obj,"is_active"):obj.is_active=True
        obj.save(using=conn.alias)
        buyer_id=int(obj.pk)
        digest=hashlib.sha256(ident.encode("ascii")).hexdigest()
        issued=_now_naive()
        expires=issued+timedelta(seconds=COOKIE_LIFETIME)
        with conn.cursor() as cursor:
            cursor.execute(
              """INSERT INTO mpw_walletless_trx_guest_claim_v1
                (buyer_id,secret_sha256,created_at,expires_at)
                VALUES (%s,%s,%s,%s)""",
              [buyer_id,digest,issued,expires])
            claim_id=int(cursor.lastrowid)
        token=signing.dumps({"id":claim_id,"secret":ident},salt=COOKIE_SALT)
        if len(token)>CLAIM_MAX_LENGTH:
            raise PaymentHold("Guest token encoding exceeded safe cookie limit")
        return buyer_id,token


def install_guest_cookie(response,token):
    """Browser owns only the signed claim, not a permanent login session."""
    if not isinstance(token,str) or len(token)>CLAIM_MAX_LENGTH:
        raise PaymentHold("Invalid guest cookie")
    response.set_cookie(
        COOKIE_NAME,token,max_age=COOKIE_LIFETIME,path=COOKIE_PATH,
        secure=True,httponly=True,samesite="Lax",
    )
    return response

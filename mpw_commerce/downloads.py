"""Authenticated, no-cache digital-file delivery for PAID buyer entitlements.

Never expose filesystem paths, attach a public PDF link, or trust customer-
supplied file names. The private asset root is outside the web document root.
The page is not routed on any live domain unless explicitly enabled later.
"""
from pathlib import Path
import os
import stat

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.models import OrderItem
from .entitlements import can_access_purchased_digital_item

ACCEPTED_SUFFIXES=frozenset((".pdf",".zip",".epub",".mp3",".mp4"))
DOMAIN_ALLOWLIST=frozenset(("mojplaywin.com","www.mojplaywin.com"))


def _private_file(item):
    metadata=item.product.metadata
    if not isinstance(metadata,dict):
        raise FileNotFoundError("No downloadable digital asset")
    config=metadata.get("mpw_commerce")
    if not isinstance(config,dict):
        raise FileNotFoundError("Digital file unconfigured")
    raw=config.get("private_file")
    root_setting=getattr(settings,"MPW_COMMERCE_PRIVATE_ASSET_ROOT",None)
    if (not isinstance(raw,str) or not raw or len(raw)>250
        or not isinstance(root_setting,str) or not root_setting.startswith("/")):
        raise FileNotFoundError("Private product asset not configured")
    rel=Path(raw)
    if rel.is_absolute() or any(p in (".","..") for p in rel.parts):
        raise FileNotFoundError("Unsafe product asset reference")
    root=Path(root_setting)
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError("Untrusted private asset root")
    candidate=root/rel
    for path in (candidate,)+tuple(candidate.parents):
        if path==root.parent:break
        if path.is_symlink():
            raise FileNotFoundError("Symlink asset access not allowed")
    actual=candidate.resolve(strict=True)
    root_actual=root.resolve(strict=True)
    if not actual.is_relative_to(root_actual) or actual.suffix.lower() not in ACCEPTED_SUFFIXES:
        raise FileNotFoundError("Asset outside private allowed types")
    st=actual.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:
        raise FileNotFoundError("Asset is not a trusted private regular file")
    return actual


@login_required
@never_cache
@require_GET
def download_paid_item(request,item_id):
    if getattr(settings,"MPW_COMMERCE_DOWNLOADS_ENABLED",False) is not True:
        raise Http404
    if not request.is_secure() or request.get_host().split(":")[0].lower() not in DOMAIN_ALLOWLIST:
        return HttpResponseForbidden("Secure MojPlayWin domain required")
    if not can_access_purchased_digital_item(item_id,request.user.pk):
        raise Http404
    item=OrderItem.objects.select_related("product").filter(pk=item_id).first()
    if item is None:
        raise Http404
    try:
        path=_private_file(item)
        fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW)
        file_handle=os.fdopen(fd,"rb")
    except (OSError,ValueError) as exc:
        raise Http404 from exc
    result=FileResponse(file_handle,as_attachment=True,filename=path.name)
    result["Cache-Control"]="no-store, private"
    result["X-Content-Type-Options"]="nosniff"
    return result

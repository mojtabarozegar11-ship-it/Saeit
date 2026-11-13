"""Paid-only guest download, scoped to a signed receipt on the same browser.

The opened descriptor, rather than the previously inspected pathname, must be
verified: a path can be replaced between eligibility inspection and os.open().
"""
import os
import stat
from django.http import Http404, FileResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .guest_receipts import COOKIE, get_order
from .guest_product import approved_item


@never_cache
@require_GET
def download(request):
    if (not request.is_secure() or
            request.get_host().split(":")[0].lower() not in
            ("mojplaywin.com", "www.mojplaywin.com")):
        raise Http404
    order = get_order(request.COOKIES.get(COOKIE))
    if order is None or order["status"] != "paid" or not order["txid"]:
        raise Http404
    product, path = approved_item(order["product_id"])

    # No symlink following, and do not allow a FIFO/device to block a worker
    # or expose non-file content even if the pathname was swapped after audit.
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise Http404("Private product file unavailable") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise Http404("Private product file is not regular")
        # Reject path replacement between product approval and descriptor open.
        current = path.stat()
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise Http404("Private product file changed during delivery")
        stream = os.fdopen(fd, "rb")
        fd = -1
        try:
            response = FileResponse(stream, as_attachment=True, filename=path.name)
        except Exception:
            stream.close()
            raise
    except OSError as exc:
        raise Http404("Private product file unavailable") from exc
    finally:
        if fd >= 0:
            os.close(fd)

    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response

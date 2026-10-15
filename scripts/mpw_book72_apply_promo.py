"""Update book 72's owner-declared pricing without publishing or enabling payment."""
import json
import os
from decimal import Decimal
from pathlib import Path
from tempfile import mkstemp

ASSET="store/chess-improvement/MojPlayWin_Chess_Master_Editorial_Working_741p.pdf"
SHA="fbe687e6ef947b827bf524fe32c3a23cae6618424134ac4ac3f1c3d094290cfb"
PRICING={
    "list_price_usd":"30.00",
    "sale_price_usd":"7.50",
    "discount_amount_usd":"22.50",
    "discount_percent":75,
    "source":"owner-declared-list-price",
}


def update_book72_promo(*, backup_root=None):
    from django.apps import apps
    from django.conf import settings
    from django.db import transaction

    if settings.DEBUG is not False:
        raise RuntimeError("Expected safe production configuration")
    for gate in ("MPW_COMMERCE_RELEASE_READY","MPW_COMMERCE_INVOICING_ENABLED",
                 "MPW_COMMERCE_SETTLEMENT_ENABLED","MPW_COMMERCE_DOWNLOADS_ENABLED"):
        if getattr(settings, gate, False) is True:
            raise RuntimeError("Refuse to edit live product promotion during active checkout")

    Product=apps.get_model("core","Product")
    with transaction.atomic():
        item=Product.objects.select_for_update().select_related("knowledge_article").get(pk=72)
        if item.active or item.owner_id is None or not item.knowledge_article_id or item.knowledge_article.published:
            raise RuntimeError("Private draft with owner and unpublished article required")
        if item.price!=Decimal("7.50") or item.currency!="USD" or item.product_type!="digital_book":
            raise RuntimeError("Refuse unexpected checkout price")
        meta=item.metadata if isinstance(item.metadata,dict) else {}
        commerce=meta.get("mpw_commerce",{})
        if (not isinstance(commerce,dict) or commerce.get("enabled") is not False
                or commerce.get("private_file")!=ASSET or meta.get("asset_sha256")!=SHA):
            raise RuntimeError("Missing verified 741-page private binding")
        if meta.get("pricing")==PRICING:
            return "already_verified"
        folder=Path(backup_root) if backup_root else Path.home()/".mpw-book72-private-rollback"
        if folder.is_symlink():
            raise RuntimeError("Backup path cannot be symbolic link")
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd,tmp=mkstemp(prefix="book72-promo-prechange-",suffix=".json",dir=str(folder))
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as dest:
                json.dump({"product_id":72,"metadata":meta,"price":str(item.price),
                           "active":item.active},dest)
                dest.flush()
                os.fsync(dest.fileno())
            os.chmod(tmp,0o600)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        updated=dict(meta)
        updated["pricing"]=dict(PRICING)
        item.metadata=updated
        item.full_clean()
        item.save(update_fields=["metadata","updated_at"])
        assert item.price==Decimal("7.50") and not item.active
        return "draft_promotion_saved"


if __name__=="__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    django.setup()
    print("BOOK72_PROMO="+update_book72_promo())
    print("BOOK72_REGULAR_USD=30.00")
    print("BOOK72_DISCOUNT_USD=22.50")
    print("BOOK72_DISCOUNT_PERCENT=75")
    print("BOOK72_ACTUAL_USD=7.50")
    print("BOOK72_SALES_REMAIN_OFF=YES")

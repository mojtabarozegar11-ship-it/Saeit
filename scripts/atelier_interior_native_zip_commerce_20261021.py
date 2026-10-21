#!/usr/bin/env python3
"""Owner-authorized, exact Product 879 ZIP bridge to existing MojPlayWin commerce; rollback scoped."""
from __future__ import annotations
import copy,hashlib,json,os,pwd,stat,sys,shutil
from pathlib import Path
from types import SimpleNamespace

APP=Path("/home/zomorod2/Saeit-staging")
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
SNAP=SAFE/"atelier-879-before-native-zip-commerce.json"
SKU="atelier-interior-kit-v1"
TITLE="Atelier Interior — Client-Ready Website Kit"
SHA="20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
FILENAME="atelier-interior-kit-v1-original-vector-edition.zip"
REL=".atelier_owner_879_original_vector_20261021/"+FILENAME
ARTICLE_SLUG="atelier-interior-kit-original-vector-edition-879"

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda:f.read(131072),b""):h.update(data)
    return h.hexdigest()

def setup():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("WRONG_OWNER_USER")
    if not APP.is_dir() or APP.is_symlink() or not (APP/"manage.py").is_file():raise RuntimeError("APP_NOT_VERIFIED")
    if not SAFE.is_dir() or SAFE.is_symlink() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:raise RuntimeError("UNSAFE_SNAPSHOT_DIR")
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django;django.setup()
    from django.conf import settings
    from django.db import transaction
    from core.models import Product
    from mpw_commerce.product_checkout_page import approved_for_checkout
    root_value=getattr(settings,"MPW_COMMERCE_PRIVATE_ASSET_ROOT",None)
    if not isinstance(root_value,str) or not root_value.startswith("/"):raise RuntimeError("COMMERCE_ASSET_ROOT_NOT_CONFIGURED")
    root=Path(root_value)
    if not root.is_dir() or root.is_symlink() or not root.resolve().is_relative_to(Path("/home/zomorod2")):
        raise RuntimeError("WRONG_COMMERCE_ASSET_ROOT")
    target=root/REL
    if target.is_symlink() or (target.parent.exists() and (target.parent.is_symlink() or not target.parent.is_dir())):
        raise RuntimeError("COMMERCE_DESTINATION_UNTRUSTED")
    article_model=Product._meta.get_field("knowledge_article").remote_field.model
    return Product,article_model,transaction,approved_for_checkout,target

def guard_product(p,expected_type="website_template"):
    if p.pk!=879 or p.title!=TITLE or p.product_type!=expected_type or str(p.price)!="6.80" or p.currency!="USD" or not p.active:
        raise RuntimeError("EXACT_PRODUCT_ID_TITLE_PRICE_STATE_CHANGED")
    m=p.metadata
    if not isinstance(m,dict) or m.get("sku")!=SKU or m.get("sha256")!=SHA:
        raise RuntimeError("PRODUCT_879_ASSET_METADATA_CHANGED")
    return m

def preserve(p):
    data=json.dumps({"id":p.pk,"active":p.active,"product_type":p.product_type,
                     "knowledge_article_id":p.knowledge_article_id,"metadata":p.metadata},
                    sort_keys=True,ensure_ascii=False).encode()
    if SNAP.is_symlink():raise RuntimeError("SNAPSHOT_SYMLINK")
    if SNAP.exists():
        if digest(SNAP)!=hashlib.sha256(data).hexdigest():raise RuntimeError("EXISTING_SNAPSHOT_CONFLICT")
    else:
        with SNAP.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(data);f.flush();os.fsync(f.fileno())

def ensure_zip(original,target):
    if original.is_symlink() or not original.is_file() or digest(original)!=SHA:
        raise RuntimeError("SOURCE_ZIP_CHANGED")
    if stat.S_IMODE(original.stat().st_mode)&0o077:raise RuntimeError("SOURCE_ZIP_NOT_PRIVATE")
    if not target.parent.exists():target.parent.mkdir(mode=0o700)
    if target.parent.is_symlink() or stat.S_IMODE(target.parent.stat().st_mode)&0o077:
        raise RuntimeError("DESTINATION_DIRECTORY_NOT_PRIVATE")
    if target.exists():
        if target.is_symlink() or not target.is_file() or digest(target)!=SHA:
            raise RuntimeError("EXISTING_ZIP_CONFLICT")
    else:
        with original.open("rb") as source,target.open("xb") as dest:
            os.fchmod(dest.fileno(),0o600)
            shutil.copyfileobj(source,dest,1024*256)
            dest.flush();os.fsync(dest.fileno())
    if digest(target)!=SHA or stat.S_IMODE(target.stat().st_mode)&0o077:
        raise RuntimeError("PRIVATE_COMMERCE_ZIP_FAILED")

def fake_buyer():
    return SimpleNamespace(is_secure=lambda:True,get_host=lambda:"mojplaywin.com",
        user=SimpleNamespace(is_authenticated=True,is_active=True))

def activate():
    if os.environ.get("ATELIER_OWNER_NATIVE_ZIP_COMMERCE")!="20261021-owner-879":
        raise PermissionError("OWNER_APPROVAL_MISSING")
    Product,Article,txn,approved,target=setup()
    with txn.atomic():
        p=Product.objects.select_for_update().select_related("knowledge_article").get(pk=879)
        if p.product_type=="digital":
            if (p.title!=TITLE or str(p.price)!="6.80" or p.currency!="USD" or not p.active
                or not p.knowledge_article_id or p.knowledge_article.slug!=ARTICLE_SLUG
                or p.metadata.get("sku")!=SKU or p.metadata.get("sha256")!=SHA
                or p.metadata.get("mpw_commerce",{}).get("private_file")!=REL
                or not target.is_file() or digest(target)!=SHA or not approved(fake_buyer(),p)):
                raise RuntimeError("EXISTING_NATIVE_COMMERCE_INCONSISTENT")
            print("ATELIER_NATIVE_ZIP_COMMERCE_IDEMPOTENT=GATE_PASS_NO_NEW_WRITE")
            return
        m=guard_product(p)
        if p.knowledge_article_id is not None:raise RuntimeError("PRODUCT_ALREADY_HAS_ARTICLE")
        from core.cryptopay_checkout import _file_for
        original=_file_for(p)
        if not original:raise RuntimeError("PREVIOUS_NATIVE_DELIVERY_NOT_AVAILABLE")
        ensure_zip(Path(original),target)
        if Article.objects.filter(slug=ARTICLE_SLUG).exists():raise RuntimeError("ARTICLE_SLUG_CONFLICT")
        preserve(p)
        article=Article(title=TITLE,slug=ARTICLE_SLUG,published=True,version=1,
          content=(
          "Atelier Interior Original Vector Edition v1.1 is a downloadable ZIP of an editable, "
          "responsive interior-design studio website. Includes HTML, CSS, JavaScript, configuration, "
          "setup guide, a non-exclusive one-site/client license and five original SVG room illustrations. "
          "Buyer can edit branding, contact details and WhatsApp inquiry link. "
          "The photographs on the separate demonstration website are NOT included; "
          "no hosting, custom installation or bespoke support is included. "
          "USD 6.80 introductory sale price. Payment and private download follow an order-specific "
          "verified ETH/TRX invoice. Do not send cryptocurrency without a verified invoice."
          ))
        article.full_clean();article.save()
        updated=copy.deepcopy(m)
        updated["original_product_category"]="website_template"
        updated["catalog_category"]="Editable Website Kit"
        updated["digital_asset_format"]="ZIP"
        updated["checkout_enabled"]=True
        updated["sales_enabled"]=True
        updated["mpw_commerce"]["private_file"]=REL
        updated["mpw_commerce"]["enabled"]=True
        updated["mpw_commerce"]["fulfillment"]="digital"
        p.product_type="digital";p.knowledge_article=article;p.metadata=updated
        p.full_clean()
        if not approved(fake_buyer(),p):raise RuntimeError("NATIVE_REAL_COMMERCE_CHECKOUT_GATE_REJECTED_879")
        p.save(update_fields=["product_type","knowledge_article","metadata","updated_at"])
    check=Product.objects.select_related("knowledge_article").get(pk=879)
    if not approved(fake_buyer(),check):raise RuntimeError("SAVED_CHECKOUT_GATE_NOT_READY")
    print("ATELIER_NATIVE_ZIP_COMMERCE_READY="+json.dumps({
       "product_id":879,"article_id":check.knowledge_article_id,"price_usd":"6.80",
       "public":check.active,"zip_sha_verified":True,"real_checkout_gate":True,
       "signed_in_buyer_simulated_without_order":True,"real_customer_paid_tested":False,
       "safe_metadata_snapshot":True},sort_keys=True))

def rollback():
    if os.environ.get("ATELIER_OWNER_NATIVE_ZIP_ROLLBACK")!="20261021-owner-879":
        raise PermissionError("ROLLBACK_APPROVAL_MISSING")
    Product,Article,txn,approved,target=setup()
    if SNAP.is_symlink() or not SNAP.is_file():raise RuntimeError("NO_SNAPSHOT")
    state=json.loads(SNAP.read_text("utf8"))
    if state.get("id")!=879 or state.get("product_type")!="website_template" or state.get("knowledge_article_id") is not None:
        raise RuntimeError("NOT_EXACT_SNAPSHOT")
    with txn.atomic():
        p=Product.objects.select_for_update().get(pk=879)
        if p.title!=TITLE or p.product_type!="digital" or p.metadata.get("sku")!=SKU:
            raise RuntimeError("ROLLBACK_CURRENT_PRODUCT_CONFLICT")
        if not p.knowledge_article_id or p.knowledge_article.slug!=ARTICLE_SLUG:
            raise RuntimeError("ROLLBACK_CURRENT_ARTICLE_CONFLICT")
        article=p.knowledge_article
        p.product_type=state["product_type"]
        p.knowledge_article_id=None
        p.metadata=state["metadata"]
        p.active=state["active"]
        p.full_clean();p.save(update_fields=["active","product_type","knowledge_article","metadata","updated_at"])
        article.published=False
        article.save(update_fields=["published","updated_at"])
    print("ATELIER_NATIVE_ZIP_COMMERCE_ROLLED_BACK=EXACT_PRODUCT_ONLY")

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)==2 else ""
    if mode=="selftest":
        assert len(SHA)==64 and REL.endswith(".zip") and ARTICLE_SLUG
        print("ATELIER_NATIVE_ZIP_BRIDGE_SELFTEST=PASS")
    elif mode=="activate":activate()
    elif mode=="rollback":rollback()
    else:raise SystemExit("selftest|activate|rollback")

#!/usr/bin/env python3
"""Privacy-safe classifier for private file resolver on product 879."""
import ast,copy,inspect,json,os,sys
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ["PYTHONDONTWRITEBYTECODE"]="1";os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from core.models import Product
import core.cryptopay_checkout as checkout
resolve=getattr(checkout,"_file_for")
def summary(p):
    try:
        v=resolve(p)
        if v is None:return {"resolved":False,"type":"None"}
        q=Path(v)
        return {"resolved":True,"type":type(v).__name__,"suffix":q.suffix.lower(),
            "exists":q.is_file(),"is_symlink":q.is_symlink(),"under_private_root":str(q).startswith("/home/zomorod2/.private_"),
            "sha_matches_product":bool(q.is_file() and not q.is_symlink() and
              __import__("hashlib").sha256(q.read_bytes()).hexdigest()==p.metadata.get("sha256"))}
    except Exception as e:return {"resolved":False,"error_type":type(e).__name__}
p=Product.objects.get(pk=879)
q=copy.copy(p);q.active=True;q.metadata=copy.deepcopy(p.metadata)
q.metadata.update({"quality_approved":True,"checkout_enabled":True,"payment_live":True,
                    "private_asset_installed":True,"mpw_private_file_prepared":True,"fulfillment_status":"ready"})
q.metadata["mpw_commerce"]["enabled"]=True
ref=Product.objects.get(pk=225)
try:
    src=inspect.getsource(resolve);tree=ast.parse(src)
    names=sorted({a for a in resolve.__code__.co_names if not a.startswith("__")})
    literals=sorted({n.value for n in ast.walk(tree) if isinstance(n,ast.Constant)
         and isinstance(n.value,str) and 1<=len(n.value)<=48 and "/" not in n.value and "\\" not in n.value
         and not any(w in n.value.lower() for w in ("password","token","secret","private","wallet","key"))})
except Exception:
    names=[];literals=[]
print("ATELIER_PRIVATE_FILE_RESOLVER="+json.dumps({
    "original_inactive_879":summary(p),"candidate_in_memory_879":summary(q),"existing_active_book_225":summary(ref),
    "safe_attribute_names":names,"safe_string_constants":literals,
    "no_sensitive_file_paths_printed":True,"no_database_mutations":True},sort_keys=True))

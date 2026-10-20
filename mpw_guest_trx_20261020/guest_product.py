"""Digital book eligibility and original private file resolver."""
from types import SimpleNamespace
from django.http import Http404
from django.shortcuts import get_object_or_404
from core.models import Product
from mpw_commerce.fulfillment import _private_file

BOOKS=frozenset((72,225))
FLAGS=("asset_verified","license_verified","quality_approved","factory_publication_permission")
def approved_item(pk):
 if pk not in BOOKS:raise Http404
 obj=get_object_or_404(Product.objects.select_related("knowledge_article"),pk=pk,active=True)
 md=obj.metadata
 cfg=md.get("mpw_commerce") if type(md) is dict else None
 if (type(cfg) is not dict or cfg.get("enabled") is not True or cfg.get("fulfillment")!="digital"
    or any(md.get(k) is not True for k in FLAGS) or obj.currency!="USD"
    or not (0<obj.price<=1000) or not obj.knowledge_article_id
    or obj.knowledge_article.published is not True):
  raise Http404("Product unavailable")
 try:path=_private_file(SimpleNamespace(product=obj))
 except (ValueError,OSError):raise Http404("File unavailable")
 if not path.is_file() or path.is_symlink():raise Http404("File unavailable")
 return obj,path

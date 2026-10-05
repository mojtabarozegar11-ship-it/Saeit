"""Bounded tools for the autonomous digital product factory."""
from django.utils import timezone

from .models import FactoryMarketEligibility, Product
from .tool_gateway import ToolGateway, ToolSpec

LANGUAGES = ("en","zh-hans","hi","es","fr","ar","bn","pt","ru","ur","id","de","ja","sw","mr","te","tr","ta","vi","ko")
SUPPORTED_LOCALES = LANGUAGES + ("fa",)


def _product(payload):
    pid = payload.get("product_id")
    if not pid:
        raise ValueError("product_id is required")
    return Product.objects.get(pk=pid)


def product_research(payload):
    sources = payload.get("sources") or []
    if len(sources) < 2 or not all(isinstance(x, dict) and x.get("url") and x.get("finding") for x in sources):
        raise ValueError("At least two source-backed market findings are required.")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    product = Product.objects.create(
        title=title, product_type=str(payload.get("product_type") or "digital"),
        price=0, currency=str(payload.get("currency") or "USD"), active=False,
        metadata={"factory_state":"researched","research":{"sources":sources,"market":payload.get("market","global")},
                  "created_at":timezone.now().isoformat(),"languages_target":list(LANGUAGES)}
    )
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"researched","evidence_count":len(sources)}


def opportunity_score(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="researched":
        raise ValueError("Product must have verified research before scoring.")
    score=payload.get("score")
    try: score=float(score)
    except (TypeError,ValueError): raise ValueError("numeric score is required")
    if not 0 <= score <= 100: raise ValueError("score must be between 0 and 100")
    product.metadata={**product.metadata,"factory_state":"scored","opportunity":{"score":score,"rationale":str(payload.get("rationale") or "")}}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"scored","score":score}


def product_spec(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="scored":
        raise ValueError("Product must be scored before specification.")
    spec=payload.get("spec") or {}
    if not isinstance(spec,dict) or not spec.get("problem") or not spec.get("acceptance_criteria"):
        raise ValueError("spec.problem and spec.acceptance_criteria are required")
    product.metadata={**product.metadata,"factory_state":"specified","spec":spec}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"specified"}


def product_build_record(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="specified":
        raise ValueError("Product must be specified before build recording.")
    artifact=payload.get("artifact") or {}
    if not isinstance(artifact,dict) or not artifact.get("ref"):
        raise ValueError("A versioned build artifact ref is required.")
    product.metadata={**product.metadata,"factory_state":"built","build":artifact}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"built","artifact":artifact}


def product_qa(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="built":
        raise ValueError("Product must be built before QA.")
    tests=payload.get("tests") or {}
    security=payload.get("security") or {}
    if tests.get("passed") is not True or security.get("passed") is not True:
        raise ValueError("Passing automated tests and security checks are required.")
    product.metadata={**product.metadata,"factory_state":"qa_passed","qa":{"tests":tests,"security":security}}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"qa_passed"}


def product_localize(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="qa_passed":
        raise ValueError("Product must pass QA before localization.")
    locales=payload.get("locales") or []
    if not locales or not all(x in SUPPORTED_LOCALES for x in locales):
        raise ValueError("At least one supported launch locale is required.")
    product.metadata={**product.metadata,"factory_state":"localized","localization":{"launch_locales":locales,"architecture_locales":list(LANGUAGES)}}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"localized","locales":locales}


def launch_candidate(payload):
    product=_product(payload)
    if product.metadata.get("factory_state")!="localized":
        raise ValueError("Product must be localized before launch candidacy.")
    requested=payload.get("markets") or []
    if not requested or not all(isinstance(x,dict) and (x.get("market_code") or x.get("country")) for x in requested):
        raise ValueError("Market codes are required; eligibility must come from the owner-reviewed registry.")
    codes = list(dict.fromkeys(str(x.get("market_code") or x.get("country")).strip().upper() for x in requested))
    registry = {
        item.market_code: item
        for item in FactoryMarketEligibility.objects.filter(
            market_code__in=codes, reviewed_by__is_superuser=True
        ).select_related("reviewed_by")
    }
    now = timezone.now()
    markets = []
    for code in codes:
        item = registry.get(code)
        if not item:
            raise ValueError(f"Market {code} has no owner-reviewed eligibility record.")
        if item.valid_until and item.valid_until <= now:
            raise ValueError(f"Market {code} eligibility review is stale.")
        if item.eligibility == FactoryMarketEligibility.ALLOWED and (
            not item.evidence_reference or not item.review_note.strip() or not item.valid_until
        ):
            raise ValueError(f"Market {code} has incomplete owner review evidence.")
        markets.append({
            "market_code": item.market_code,
            "eligibility": item.eligibility,
            "evidence_reference": item.evidence_reference,
            "reviewed_at": item.reviewed_at.isoformat(),
            "valid_until": item.valid_until.isoformat() if item.valid_until else None,
        })
    if not any(x["eligibility"]==FactoryMarketEligibility.ALLOWED for x in markets):
        raise ValueError("At least one allowed launch market is required.")
    product.metadata={**product.metadata,"factory_state":"launch_candidate","market_eligibility":markets,
                      "launch_candidate_at":timezone.now().isoformat(),"owner_publish_approval_required":True}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"launch_candidate","owner_publish_approval_required":True}


def build_factory_gateway():
    return ToolGateway([
        ToolSpec(code="product_research",handler=product_research,risk="low"),
        ToolSpec(code="product_opportunity_score",handler=opportunity_score,risk="low"),
        ToolSpec(code="product_spec",handler=product_spec,risk="medium"),
        ToolSpec(code="product_build_record",handler=product_build_record,risk="medium"),
        ToolSpec(code="product_qa",handler=product_qa,risk="medium"),
        ToolSpec(code="product_localize",handler=product_localize,risk="medium"),
        ToolSpec(code="product_launch_candidate",handler=launch_candidate,risk="medium"),
    ])

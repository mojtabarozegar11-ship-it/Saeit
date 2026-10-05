"""Bounded tools for the autonomous digital product factory."""
from django.utils import timezone

from .models import AgentTask, FactoryArtifact, FactoryMarketEligibility, FactoryRun, Product
from .tool_gateway import ToolGateway, ToolSpec, consume_factory_invocation
from .factory_contracts import FactoryAgentOutput
from .factory_contracts import canonical_digest

LANGUAGES = ("en","zh-hans","hi","es","fr","ar","bn","pt","ru","ur","id","de","ja","sw","mr","te","tr","ta","vi","ko")
SUPPORTED_LOCALES = LANGUAGES + ("fa",)


def _merge_output(payload, action):
    consume_factory_invocation(payload, action)
    output = payload.get("__agent_output")
    if not isinstance(output, FactoryAgentOutput) or output.action != action:
        raise ValueError("A validated Factory adapter output is required.")
    # Trusted adapter values are kept distinct until this tool boundary; user
    # Task intent is never permitted to supply or override them.
    return {**payload, **output.values}


def _product(payload):
    pid = payload.get("product_id")
    if not pid:
        raise ValueError("product_id is required")
    return Product.objects.get(pk=pid)


def product_research(payload):
    payload = _merge_output(payload, "product_research")
    sources = payload.get("sources") or []
    if not sources or not all(isinstance(x, dict) and x.get("url") and x.get("finding") for x in sources):
        raise ValueError("At least one traceable source-backed finding is required; adequacy is decided by Validation.")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    research = {"sources":sources,"market":payload.get("market","global"),
        "evidence":payload.get("evidence",[]),"research_project_id":payload.get("research_project_id"),
        "research_report_id":payload.get("research_report_id"),"research_provider":payload.get("research_provider"),
        "real_research":payload.get("real_research") is True,"research_plan":payload.get("research_plan") or {}}
    product = Product.objects.filter(pk=payload.get("product_id")).first() if payload.get("product_id") else None
    if product:
        if product.metadata.get("factory_state") != "needs_research":
            raise ValueError("Bounded re-research is only allowed after a current Validation request.")
        metadata = dict(product.metadata)
        for key in ("opportunity", "validation", "spec", "build", "qa", "localization", "market_eligibility"):
            metadata.pop(key, None)
        product.metadata = {**metadata,"factory_state":"researched","research":research,
            "created_at":metadata.get("created_at", timezone.now().isoformat()),"languages_target":list(LANGUAGES)}
        product.save(update_fields=["metadata","updated_at"])
    else:
        product = Product.objects.create(
            title=title, product_type=str(payload.get("product_type") or "digital"),
            price=0, currency=str(payload.get("currency") or "USD"), active=False,
            factory_managed=True,
            metadata={"factory_state":"researched","research":research,
                      "created_at":timezone.now().isoformat(),"languages_target":list(LANGUAGES)}
        )
    run = FactoryRun.objects.filter(run_id=payload.get("__run_id")).first()
    if run:
        run.product = product
        run.save(update_fields=["product", "updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"researched","evidence_count":len(sources),"title":product.title,"sources":sources,
            "research_provider":research["research_provider"],"real_research":research["real_research"]}


def opportunity_score(payload):
    payload = _merge_output(payload, "product_opportunity_score")
    product=_product(payload)
    if product.metadata.get("factory_state")!="researched":
        raise ValueError("Product must have verified research before scoring.")
    score=payload.get("score")
    if score is not None:
        try: score=float(score)
        except (TypeError,ValueError): raise ValueError("score must be numeric or unknown")
        if not 0 <= score <= 100: raise ValueError("score must be between 0 and 100")
    rubric = payload.get("rubric") or {}
    if rubric.get("version") != "wealth-opportunity-v1" or not rubric.get("weights") or not rubric.get("inputs"):
        raise ValueError("A versioned evidence-backed opportunity rubric is required.")
    status = payload.get("status", "needs_evidence" if score is None else "scored")
    if status not in {"scored", "needs_evidence"} or (score is None) != (status == "needs_evidence"):
        raise ValueError("Opportunity score status must distinguish a reproducible score from unknown inputs.")
    product.metadata={**product.metadata,"factory_state":"scored","opportunity":{"score":score,"status":status,"rationale":str(payload.get("rationale") or ""),"rubric":rubric}}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"scored","score":score,"status":payload.get("status","needs_evidence" if score is None else "scored"),"rationale":str(payload.get("rationale") or ""),"rubric":rubric}


def product_validation(payload):
    payload = _merge_output(payload, "product_validation")
    product = _product(payload)
    if product.metadata.get("factory_state") != "scored":
        raise ValueError("Opportunity must be scored before independent Validation.")
    validation = payload.get("validation") or {}
    outcome = validation.get("outcome")
    if outcome not in {"VALIDATED", "NEEDS_MORE_EVIDENCE", "RESEARCH_AGAIN", "REJECTED", "BLOCKED"}:
        raise ValueError("Validation outcome is missing or invalid.")
    states = {"VALIDATED":"validated", "NEEDS_MORE_EVIDENCE":"needs_research",
              "RESEARCH_AGAIN":"needs_research", "REJECTED":"rejected", "BLOCKED":"blocked"}
    product.metadata = {**product.metadata, "factory_state":states[outcome], "validation":validation}
    product.save(update_fields=["metadata", "updated_at"])
    run = FactoryRun.objects.filter(run_id=payload.get("__run_id")).first()
    if run and outcome in {"REJECTED", "BLOCKED"}:
        run.status = "rejected" if outcome == "REJECTED" else "blocked"
        run.save(update_fields=["status", "updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":states[outcome],"validation":validation}


def product_spec(payload):
    payload = _merge_output(payload, "product_spec")
    product=_product(payload)
    if product.metadata.get("factory_state")!="validated" or (product.metadata.get("validation") or {}).get("outcome") != "VALIDATED":
        raise ValueError("Product must pass current Validation before specification.")
    spec=payload.get("spec") or {}
    if not isinstance(spec,dict) or not spec.get("problem") or not spec.get("acceptance_criteria"):
        raise ValueError("spec.problem and spec.acceptance_criteria are required")
    claimed = spec.get("digest")
    if not claimed:
        raise ValueError("A canonical specification digest is required.")
    canonical = dict(spec); canonical.pop("digest", None)
    if claimed != canonical_digest(canonical):
        raise ValueError("Specification digest does not match canonical content.")
    product.metadata={**product.metadata,"factory_state":"specified","spec":spec}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"specified","spec":spec}


def product_build_record(payload):
    payload = _merge_output(payload, "product_build_record")
    product=_product(payload)
    if product.metadata.get("factory_state")!="specified":
        raise ValueError("Product must be specified before build recording.")
    artifact=payload.get("artifact") or {}
    if not isinstance(artifact,dict) or not artifact.get("ref"):
        raise ValueError("A versioned build artifact ref is required.")
    run = FactoryRun.objects.filter(run_id=payload.get("__run_id")).first()
    task = AgentTask.objects.filter(pk=payload.get("__task_id")).first()
    if run and task:
        version = run.current_artifact_version + 1
        artifact_row = FactoryArtifact.objects.create(
            product=product, run=run, created_by_task=task, version=version,
            reference=str(artifact["ref"]), content_digest=str(artifact.get("sha256") or ""),
            spec_version=run.current_spec_version,
        )
        run.current_artifact_version = version
        run.save(update_fields=["current_artifact_version", "updated_at"])
        artifact = {**artifact, "version": version, "artifact_id": artifact_row.pk}
    else:
        version = 0
    product.metadata={**product.metadata,"factory_state":"built","build":artifact}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"built","artifact":artifact,"artifact_version":version}


def product_qa(payload):
    payload = _merge_output(payload, "product_qa")
    product=_product(payload)
    if product.metadata.get("factory_state")!="built":
        raise ValueError("Product must be built before QA.")
    tests=payload.get("tests") or {}
    security=payload.get("security") or {}
    if tests.get("passed") is not True or security.get("passed") is not True:
        raise ValueError("Passing automated tests and security checks are required.")
    product.metadata={**product.metadata,"factory_state":"qa_passed","qa":{"tests":tests,"security":security}}
    product.save(update_fields=["metadata","updated_at"])
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"qa_passed","tests":tests,"security":security}


def product_localize(payload):
    payload = _merge_output(payload, "product_localize")
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
    payload = _merge_output(payload, "product_launch_candidate")
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
    return {"verified_effect":True,"product_id":product.pk,"factory_state":"launch_candidate","owner_publish_approval_required":True,"markets":markets}


def build_factory_gateway():
    return ToolGateway([
        ToolSpec(code="product_research",handler=product_research,risk="low"),
        ToolSpec(code="product_opportunity_score",handler=opportunity_score,risk="low"),
        ToolSpec(code="product_validation",handler=product_validation,risk="low"),
        ToolSpec(code="product_spec",handler=product_spec,risk="medium"),
        ToolSpec(code="product_build_record",handler=product_build_record,risk="medium"),
        ToolSpec(code="product_qa",handler=product_qa,risk="medium"),
        ToolSpec(code="product_localize",handler=product_localize,risk="medium"),
        ToolSpec(code="product_launch_candidate",handler=launch_candidate,risk="medium"),
    ])

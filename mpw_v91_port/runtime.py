"""MojPlayWin-only adaptor for SHA-verified V91 engines.

Pure, bounded and review-only. No factory, Django models, network, payment,
filesystem writes, scheduler, publishing or other tenant imports.
"""
import re
from urllib.parse import urlsplit

MAX_BODY=12000
MAX_TITLE=180
MAX_SUMMARY=650
MAX_SOURCES=12
MAIN_HOSTS=frozenset(("mojplaywin.com","www.mojplaywin.com"))

class MojPlayWinAgentInputError(ValueError):
    pass

def valid_main_host(host):
    if not isinstance(host,str):
        return False
    return host.lower().split(":",1)[0].rstrip(".") in MAIN_HOSTS

def _validate(source):
    if not isinstance(source,dict):
        raise MojPlayWinAgentInputError("invalid_payload")
    # Only original local extraction-based agent modes, no external LLM calls.
    kind=source.get("kind","research_digest")
    if kind != "research_digest":
        raise MojPlayWinAgentInputError("unsupported_agent_kind")
    title=source.get("title","")
    summary=source.get("summary","")
    body=source.get("body","")
    sources=source.get("sources",[])
    if (not isinstance(title,str) or not 5<=len(title)<=MAX_TITLE
        or not isinstance(summary,str) or not 35<=len(summary)<=MAX_SUMMARY
        or not isinstance(body,str) or not 250<=len(body)<=MAX_BODY
        or not isinstance(sources,list) or not 1<=len(sources)<=MAX_SOURCES):
        raise MojPlayWinAgentInputError("input_size_invalid")
    for s in sources:
        if not isinstance(s,str) or len(s)>400:
            raise MojPlayWinAgentInputError("invalid_reference")
        try:
            parsed=urlsplit(s)
        except ValueError as exc:
            raise MojPlayWinAgentInputError("invalid_reference") from exc
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            raise MojPlayWinAgentInputError("only_public_https_references")
    # Do not fetch URLs. They are annotations supplied with verified content.
    return kind,title,summary,body,sources

def review_draft(source):
    kind,title,summary,body,sources=_validate(source)
    # Retain V91's original Persian-only safety contract.
    from .legacy.portal.agent_engine import build_output
    from .legacy.site_master.bridge import route_once

    def perform_review():
        return build_output(kind,title,summary,body,sources,"fa")

    result=route_once("mpw-v91-review-20261018",perform_review)
    if not isinstance(result,dict) or result.get("provenance")!="published_site_article":
        raise MojPlayWinAgentInputError("invalid_agent_result")
    cleaned={k:result[k] for k in (
        "title","summary","body","sources","provenance","engine_version"
    ) if k in result}
    cleaned["review_required"]=True
    cleaned["published"]=False
    cleaned["sale_ready"]=False
    cleaned["tenant"]="mojplaywin-main"
    cleaned["legacy_origin"]="V91-master-gen64"
    return cleaned

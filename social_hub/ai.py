"""Optional ChatGPT/OpenAI Responses API copywriting; NEVER auto-publishes generated text."""
from __future__ import annotations
import json
import os
import re

from .adapters import Blocked, Uncertain
from .catalog import BRANDS, RESTRICTED_HANDLES, platform
from .transport import http_transport

SCHEMA = {
    "type":"object","additionalProperties":False,
    "properties":{
        "variants":{"type":"array","minItems":1,"maxItems":6,"items":{
            "type":"object","additionalProperties":False,
            "properties":{"platform":{"type":"string"},"text":{"type":"string"},
                          "notes":{"type":"string"}},
            "required":["platform","text","notes"]}},
        "claims_to_verify":{"type":"array","items":{"type":"string"}},
    },
    "required":["variants","claims_to_verify"],
}
SYSTEM = (
    "You are a multilingual social copywriter working for three distinct owner-controlled brands. "
    "Output only ready-to-review DRAFTS. Do not invent facts, research findings, scientific "
    "credentials, product availability, prices, metrics, endorsements, sales claims, testimonials, "
    "or certifications. Never mention the restricted handle dr.mojtaba.rozegar. "
    "Avoid unsolicited bulk marketing, manipulative targeting, and unverified investment claims. "
    "Keep each post within its platform's normal limits; no remote publication or commitment. "
    "Flag any claims that need independent evidence in claims_to_verify."
)
def propose(*, brief, brand, platforms, language="en", env=None, transport=None,
            explicit_api_consent=False):
    env = os.environ if env is None else env
    if explicit_api_consent is not True:
        raise Blocked("Explicit approval required before sending source briefs to OpenAI")
    if brand not in BRANDS or language not in ("fa","en","ar","de","ru","fr","es","tr"):
        raise Blocked("Invalid brand or language")
    if not isinstance(brief,str) or not 25 <= len(brief) <= 8000:
        raise Blocked("Human-supplied brief must be between 25 and 8000 characters")
    if any(term in brief.casefold() for term in RESTRICTED_HANDLES):
        raise Blocked("Restricted promotional account")
    if not isinstance(platforms,(list,tuple)) or not 1 <= len(platforms) <= 6:
        raise Blocked("Select 1-6 official publication targets")
    if not all(isinstance(k,str) and platform(k).sendable for k in platforms):
        raise Blocked("Unsupported automatic publication platform")
    key = env.get("MPW_SOCIAL_OPENAI_API_KEY","")
    if not key.startswith("sk-") or len(key)<20:
        raise Blocked("Private OpenAI API key missing")
    model = env.get("MPW_SOCIAL_OPENAI_MODEL","gpt-4.1-mini")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}",model):
        raise Blocked("Invalid model name")
    body = {
        "model":model,"store":False,
        "instructions":SYSTEM,
        "input":"Brand: "+brand+"\nLanguage: "+language+"\nPlatforms: "+",".join(platforms)+
                "\nOWNER-SUPPLIED VERIFIED FACTS AND BRIEF:\n"+brief,
        "text":{"format":{"type":"json_schema","name":"social_review_drafts",
                           "strict":True,"schema":SCHEMA}},
        "max_output_tokens":1500,
    }
    send = http_transport if transport is None else transport
    result=send("POST","https://api.openai.com/v1/responses",body,
                {"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    if not 200 <= result.status < 300 or result.payload.get("status")!="completed":
        raise Uncertain("AI provider did not return a completed result")
    raw = []
    for item in result.payload.get("output",[]):
        if isinstance(item,dict):
            for part in item.get("content",[]):
                if isinstance(part,dict) and part.get("type")=="output_text":
                    raw.append(part.get("text",""))
    try:
        decoded = json.loads("".join(raw))
    except (ValueError,TypeError):
        raise Uncertain("AI output was not structured") from None
    if not isinstance(decoded,dict) or not isinstance(decoded.get("variants"),list):
        raise Uncertain("AI schema invalid")
    variants=[]
    for v in decoded["variants"]:
        if not isinstance(v,dict) or v.get("platform") not in platforms:
            raise Uncertain("AI suggested a platform outside the requested accounts")
        copy=v.get("text")
        if not isinstance(copy,str) or not 1 <= len(copy) <= 40000:
            raise Uncertain("AI returned invalid copy")
        if any(x in copy.casefold() for x in RESTRICTED_HANDLES):
            raise Uncertain("AI output violated protected-account policy")
        variants.append({"platform":v["platform"],"text":copy,
                         "notes":str(v.get("notes",""))[:500]})
    if not variants or len(variants)>6:
        raise Uncertain("AI returned invalid number of variants")
    return {"brand":brand,"language":language,"variants":variants,
            "claims_to_verify":decoded.get("claims_to_verify",[])[:20],
            "human_approval_required":True,"published":False,
            "source":"OpenAI Responses API; private key, owner consent required"}

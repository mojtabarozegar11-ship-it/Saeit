#!/usr/bin/env python3
"""F23 customer-use offline evidence retrieval assistant, not a generative AI model.

Returns exact answers from locally bundled original playbook cards with explicit
source IDs, or abstains. No network, external AI API, shell, credentials or writes.
This is a bounded *technical assistant prototype*, not human expert advice.
Python 3.8+ stdlib.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
ABSTAIN = "Not enough verified information in this local playbook to answer."

def terms(value):
    if not isinstance(value,str):
        return []
    return [m.group().casefold() for m in TOKEN.finditer(value) if len(m.group())>1]

def check_cards(cards):
    if not isinstance(cards,list) or len(cards)!=48:
        raise ValueError("F23_EXPECTED_48_VERIFIABLE_KNOWLEDGE_CARDS")
    ids=set()
    for item in cards:
        if not isinstance(item,dict) or set(item)!={"id","topic","scenario","question","answer","scope"}:
            raise ValueError("F23_CARD_SCHEMA")
        ident=item["id"]
        if not isinstance(ident,str) or not re.fullmatch(r"[a-z][a-z0-9_]{4,65}",ident) or ident in ids:
            raise ValueError("F23_CARD_ID")
        if any(not isinstance(item[key],str) or not 4<=len(item[key])<=1800
               for key in ("topic","scenario","question","answer","scope")):
            raise ValueError("F23_CARD_CONTENT")
        if item["scope"]!="synthetic_offline_operations_not_professional_advice":
            raise ValueError("F23_CARD_SCOPE")
        ids.add(ident)
    return cards

def answer(question,cards):
    check_cards(cards)
    if not isinstance(question,str) or not 4<=len(question)<=700:
        return {"status":"insufficient_evidence","answer":ABSTAIN,"source_ids":[],
                "commercially_certified":False}
    query=Counter(terms(question))
    # Ignore common English interrogatives, to reduce spurious retrieval.
    stop={"what","which","where","why","how","can","could","should","would","is","are",
          "the","for","and","with","when","this","that","your","from","into","a","an",
          "do","does","please","tell","me","about","offline","factory","assistant",
          "procedure","handling"}
    query={w:c for w,c in query.items() if w not in stop}
    docs=[set(terms(row["topic"]+" "+row["scenario"]+" "+row["question"]))-stop
          for row in cards]
    df=Counter(w for doc in docs for w in doc)
    ranked=[]
    for i,row in enumerate(cards):
        common=set(query).intersection(docs[i])
        # Stable BM25-style positive IDF. Generic common words contribute
        # almost nothing rather than penalizing a genuinely exact local query.
        # We intentionally do not infer quality from returned text.
        score=sum(math.log(1.0+(48-df[word]+0.5)/(df[word]+0.5)) for word in common)
        # Query must provide meaningful details instead of broad suggestions.
        ranked.append((score,len(common),row["id"],i))
    best=max(ranked,key=lambda x:(x[0],x[1],x[2]))
    if best[1]<2 or best[0]<2.0:
        return {"status":"insufficient_evidence","answer":ABSTAIN,"source_ids":[],
                "commercially_certified":False}
    picked=cards[best[3]]
    return {"status":"retrieved","answer":picked["answer"],"source_ids":[picked["id"]],
            "evidence_scope":picked["scope"],"commercially_certified":False}

def main(argv=None):
    p=argparse.ArgumentParser(description="Bounded local playbook retrieval, no API calls")
    p.add_argument("--knowledge",default=str(Path(__file__).with_name("knowledge.json")))
    p.add_argument("--question",required=True)
    args=p.parse_args(argv)
    path=Path(args.knowledge)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1500000:
        raise ValueError("F23_KNOWLEDGE_FILE_UNTRUSTED")
    cards=json.loads(path.read_text(encoding="utf8"))
    print(json.dumps(answer(args.question,cards),ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()

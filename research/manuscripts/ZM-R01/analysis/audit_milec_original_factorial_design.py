#!/usr/bin/env python3
"""Read-only original-source audit. Does not redistribute Milec's DOCX or assert novelty."""
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MD5 = "d4ff896311410ddb3531d68295a69692"
NAME = "Wheat responses to combined drought, heat, and elevated CO2.docx"
URLS = [
    "https://zenodo.org/api/records/16229021/files/" + urllib.parse.quote(NAME) + "/content",
    "https://zenodo.org/records/16229021/files/" + urllib.parse.quote(NAME) + "?download=1",
]
KEYWORDS = {
    "count_model": r"DESeq2|edgeR|negative.binomial|design.formula|model.matrix|interaction.term|Wald.test|likelihood.ratio",
    "normalization": r"FPKM|RPKM|TPM|raw.count|read.count|normaliz|library.size",
    "alignment": r"HISAT|STAR|featureCounts|HTSeq|StringTie|Salmon|kallisto|reference.genome|annotation",
    "factorial": r"three.way|triple.interaction|factorial|interaction|ANOVA|combined.stress",
    "transcription_factor": r"WGCNA|co.expression|transcription.factor|gene.ontology|GO.enrichment",
    "sample": r"three.biological.replicates|biological.replicates|GS61|Alana|leaf.samples",
}
def retrieve():
    errors=[]
    for url in URLS:
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Research-source-method-audit/1.0"})
            with urllib.request.urlopen(req,timeout=90) as response:
                raw=response.read(9_000_000)
            assert raw[:2]==b"PK"
            assert hashlib.md5(raw).hexdigest()==MD5
            return raw
        except Exception as exc:
            errors.append(str(exc)[:140])
    raise RuntimeError("Source unavailable: "+repr(errors))
def paragraphs(blob):
    root=ET.fromstring(zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml"))
    ns="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return [text for p in root.iter(ns+"p") if (text:=re.sub(r"\s+"," ","".join((n.text or "") for n in p.iter(ns+"t")).strip()))]
def main():
    blob=retrieve()
    para=paragraphs(blob)
    audits={}
    for key,pat in KEYWORDS.items():
        rx=re.compile(pat,re.I)
        hits=[]
        for i,p in enumerate(para):
            matches=list(rx.finditer(p))
            if not matches: continue
            snippets=[]
            for match in matches[:4]:
                a=max(0,match.start()-60); b=min(len(p),match.end()+70)
                snippets.append(p[a:b])
            hits.append({"paragraph_index":i,"matches":len(matches),"excerpts":snippets[:4]})
        audits[key]=hits
    # Source-specific methods sections, not redistributed verbatim.
    result={
        "source":"https://zenodo.org/records/16229021",
        "source_md5":hashlib.md5(blob).hexdigest(),
        "source_paragraphs":len(para),
        "sections": [{"index":i,"heading":para[i][:100]} for i in (19,35,43,47,55,78,99) if i<len(para)],
        "keyword_evidence":audits,
        "no_inference_from_absence":True,
        "no_original_docx_in_artifact":True,
        "conclusion":"Source keyword context for expert review only; no claim of absence of any analysis, raw-count access, DEG or new biology."
    }
    Path("milec_source_detailed_method_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("SOURCE_OK",result["source_md5"],"PARAGRAPHS",len(para))
    for k,v in audits.items():
        print("METHOD",k,"PARAGRAPHS",len(v),"INDEXES",[x["paragraph_index"] for x in v[:15]])
        for h in v[:6]:
            print("CONTEXT",k,h["paragraph_index"],json.dumps(h["excerpts"][:2],ensure_ascii=False))
if __name__=="__main__":
    main()

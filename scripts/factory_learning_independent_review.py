"""Independent bounded review for 4 fixed-scope educational factory makers.

This checks original files, numeric correctness, usability structure and integrity;
it is not field research, expert, age-suitability, or legal certification.
"""
from pathlib import Path
import hashlib
import json
import zipfile
from html.parser import HTMLParser
GATES=("requirements","correctness","negative_cases","usability","accessibility",
       "security","compatibility","provenance","specialist_review","release_integrity")

class Inspect(HTMLParser):
    def __init__(self):
        super().__init__();self.tags=[];self.invalid=False;self.external=False
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        attrs=dict(attrs)
        if tag in ("script","iframe","object","embed","form","base"):self.invalid=True
        if any(k.startswith("on") for k in attrs):self.invalid=True
        if any(str(v).startswith(("https:","http:","javascript:")) for v in attrs.values()):
            self.external=True

def answer(item):
    if item["operator"]=="+":return item["a"]+item["b"]
    if item["operator"]=="-":return item["a"]-item["b"]
    if item["operator"]=="*":return item["a"]*item["b"]
    if item["operator"]=="//" and item["b"]>0 and item["a"]%item["b"]==0:
        return item["a"]//item["b"]
    raise ValueError("LEARNING_REVIEW_INVALID_OPERATOR")

def check(folder,archive,product,family):
    folder=Path(folder)
    ext={"F06":".html","F07":".html","F10":".json","F11":".docx"}[family]
    pdfs=sorted(folder.glob("*.pdf"))
    sources=[folder/(p.stem+ext) for p in pdfs]
    if len(sources)!=48 or len(pdfs)!=48:raise ValueError("LEARNING_REVIEW_EXPECTED_48_PAIRS")
    expected={p.name for p in sources+pdfs}|{"README.txt"}
    for file in sources+pdfs:
        if file.is_symlink() or not 200<=file.stat().st_size<=2_000_000:raise ValueError("LEARNING_REVIEW_UNSAFE_FILE")
        if file.suffix==".pdf":
            raw=file.read_bytes()
            if not raw.startswith(b"%PDF") or b"%%EOF" not in raw[-1024:]:
                raise ValueError("LEARNING_REVIEW_INVALID_PDF")
            continue
        if file.suffix==".html":
            text=file.read_text("utf8");doc=Inspect();doc.feed(text)
            if doc.invalid or doc.external or not all(t in doc.tags for t in ("html","main","h1")):
                raise ValueError("LEARNING_REVIEW_UNSAFE_HTML")
            if family=="F06" and (text.count("<li>")<11 or "Recovery" not in text and "Recover:" not in text):
                raise ValueError("LEARNING_REVIEW_NO_SAFETY_PROCEDURE")
            if family=="F07" and (text.count("<tr>")!=9 or "answer" not in text.lower()):
                raise ValueError("LEARNING_REVIEW_INCOMPLETE_LESSON")
        elif file.suffix==".json":
            obj=json.loads(file.read_text("utf8"));qs=obj["questions"]
            if len(qs)!=8 or len({q["expression"] for q in qs})!=8 or obj["rubric"]["total_points"]!=8:
                raise ValueError("LEARNING_REVIEW_BAD_EXAM")
            if any(answer(q)!=q["answer"] or q["b"]<=0 for q in qs):
                raise ValueError("LEARNING_REVIEW_WRONG_ANSWER")
        else:
            from docx import Document
            doc=Document(str(file))
            text="\n".join(p.text for p in doc.paragraphs)
            if len(doc.paragraphs)<20 or "Teacher key" not in text or "Rubric" not in text:
                raise ValueError("LEARNING_REVIEW_BAD_TEACHING_KIT")
        if (folder/(file.stem+".pdf")).is_file() is False:raise ValueError("LEARNING_REVIEW_MISSING_PAIRED_PDF")
    all_hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+pdfs]
    if len(set(all_hashes))!=96:raise ValueError("LEARNING_REVIEW_DUPLICATED_WORK")
    readme=folder/"README.txt"
    if not readme.is_file() or "no human expert" not in readme.read_text("utf8"):
        raise ValueError("LEARNING_REVIEW_LIMITATION_MISSING")
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=97 or set(z.namelist())!={product+"/"+p for p in expected} or z.testzip():
            raise ValueError("LEARNING_REVIEW_ARCHIVE_INVALID")
        for name in expected:
            if z.read(product+"/"+name)!=(folder/name).read_bytes():raise ValueError("LEARNING_REVIEW_CONTENT_MISMATCH")
    return {"passed":True,"checks_passed":10,"files_checked":96,
            "gates":{g:True for g in GATES},
            "scope":"automated offline format, arithmetic reference, safety-template structure and archive integrity",
            "independent_human_review":False,"classroom_trial":False,
            "professional_operations_certification":False,"commercial_release":False}

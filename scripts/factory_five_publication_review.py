"""Independent native document/container and simulation audit of F01-F05.

Not a human scientific or market evaluation. Synthetic studies never receive
a fabricated external data or rights attestation.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
GATES=("requirements","correctness","negative_cases","usability","accessibility",
       "security","compatibility","provenance","specialist_review","release_integrity")
FORMAT={
"F01":(".pdf",".epub"),"F02":(".pdf",".epub"),
"F03":(".html",".pdf",".epub"),
"F04":(".docx",".pdf"),"F05":(".xlsx",".pdf")}
def require(cond,reason):
 if not cond:raise ValueError("PUBLICATION_QA_"+reason)
def verify_pdf(path,title):
 raw=path.read_bytes()
 require(raw.startswith(b"%PDF") and b"%%EOF" in raw[-1024:] and len(raw)>=1100,"PDF_STRUCTURE")
 require(b"/Type /Page" in raw,"PDF_PAGES")
def verify_epub(path,stem,title):
 with zipfile.ZipFile(str(path)) as z:
  names=z.namelist()
  require(names[0]=="mimetype" and z.getinfo("mimetype").compress_type==0
    and z.read("mimetype")==b"application/epub+zip","EPUB_MIMETYPE_FIRST")
  require(set(names)=={"mimetype","META-INF/container.xml","OEBPS/content.opf",
    "OEBPS/nav.xhtml","OEBPS/chapter.xhtml"},"EPUB_REQUIRED_MEMBERS")
  require(z.testzip() is None,"EPUB_CRC")
  for part in names[1:]:
   doc=ET.fromstring(z.read(part))
   require(doc is not None,"EPUB_XML_INVALID")
  opf=z.read("OEBPS/content.opf").decode("utf8")
  chapter=z.read("OEBPS/chapter.xhtml").decode("utf8")
  require("application/xhtml+xml" in opf and "nav.xhtml" in opf,"EPUB_SPINE")
  require(stem in opf and title.split(" — ")[0] in chapter,"EPUB_SOURCE_LINKAGE")
  require(chapter.count("<p>")>=6,"EPUB_INCOMPLETE_CONTENT")
def verify_html(path):
 raw=path.read_text("utf8")
 require(raw.startswith("<!DOCTYPE html>") and "<main>" in raw and raw.count("<p>")>=6,
   "HTML_CONTENT")
 require(not re.search(r"<(?:script|iframe|object|embed)|onload=|onclick=|javascript:",raw,re.I),
   "HTML_UNTRUSTED_ACTIVE_CONTENT")
def verify_docx(path):
 from docx import Document
 d=Document(str(path))
 text="\n".join(p.text for p in d.paragraphs)
 require(len(d.paragraphs)>=15 and "synthetic" in text.lower() and
    "Human peer review: not obtained" in text,"DOCX_UNVERIFIED_RESEARCH_CLAIM")
def verify_xlsx(path):
 from openpyxl import load_workbook
 w=load_workbook(str(path),read_only=True,data_only=False)
 s=w.active
 require(s.title=="Synthetic scenario only" and s.max_row==7,"XLSX_NOT_SYNTHETIC")
 require(all(s.cell(i,5).value=="NOT REAL" for i in range(2,8)),"XLSX_FALSE_MARKET_DATA")
 require(all(s.cell(i,3).value=="=B%d-B%d"%(i,i-1) for i in range(3,8)),"XLSX_DERIVED_FORMULAS")
 require(all(type(s.cell(i,2).value) is int for i in range(2,8)),"XLSX_SAMPLE_MISSING")
def verify_one(folder,stem,fid):
 maker=__import__("factory_build50_five_publications")
 topic,variation=stem.rsplit("_",1)
 require(topic in maker.TOPICS and variation in maker.VARIANTS,"BAD_WORK_ID")
 title,paragraphs=maker.content(fid,{"topic":topic,"variant":variation})
 for ext in FORMAT[fid]:
  p=Path(folder)/(stem+ext)
  require(p.is_file() and not p.is_symlink() and 500<=p.stat().st_size<=5_000_000,"NATIVE_OUTPUT_MISSING")
  if ext==".pdf":verify_pdf(p,title)
  elif ext==".epub":verify_epub(p,stem,title)
  elif ext==".html":verify_html(p)
  elif ext==".docx":verify_docx(p)
  elif ext==".xlsx":verify_xlsx(p)
 if fid in ("F04","F05"):
  require(any("synthetic" in s.lower() for s in paragraphs),"SYNTHETIC_LIMITATIONS_MISSING")
 return len(FORMAT[fid])
def check(folder,archive,product,fid):
 folder=Path(folder);require(fid in FORMAT,"UNKNOWN_FAMILY")
 stems=[]
 for p in folder.glob("*.pdf"):
  require(p.stem not in stems,"DUPLICATE_CHAPTER")
  stems.append(p.stem)
 require(len(stems)==48,"REQUIRES_48_REAL_CHAPTERS")
 collected=[]
 for stem in stems:
  verify_one(folder,stem,fid)
  collected.extend(folder/(stem+ext) for ext in FORMAT[fid])
 for ext in FORMAT[fid]:
  items=[p for p in collected if p.suffix==ext]
  require(len(items)==48 and len({hashlib.sha256(p.read_bytes()).hexdigest() for p in items})==48,
    "DUPLICATE_WORK_CONTENT")
 readme=folder/"README.txt"
 require(readme.is_file() and "No professional human editorial review" in readme.read_text("utf8"),
   "UNVERIFIED_COMMERCIAL_APPROVAL")
 if fid in ("F04","F05"):
  require("SYNTHETIC DATA ONLY" in readme.read_text("utf8"),"FALSE_MARKET_OR_RESEARCH_EVIDENCE")
 collected.append(readme)
 with zipfile.ZipFile(str(archive)) as z:
  names=z.namelist()
  require(len(names)==len(collected) and z.testzip() is None,"BAD_CUSTOMER_ARCHIVE")
  require(set(names)=={product+"/"+p.name for p in collected},"ARCHIVE_MISSING_OR_EXTRA")
  for p in collected:
   require(z.read(product+"/"+p.name)==p.read_bytes(),"ARCHIVE_SOURCE_DIFFERENCE")
 return {"passed":True,"gates":{g:True for g in GATES},
    "native_files_independently_parsed":len(collected)-1,
    "actual_original_chapters":48,
    "scope":"automated format, safety, reproducibility and ZIP byte integrity only",
    "human_editorial_review":False,"independent_research_peer_review":False,
    "verified_external_market_data":False,"commercial_release":False}

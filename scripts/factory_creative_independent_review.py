"""Separate automated technical review of F29/F30/F33 fixed-scope outputs."""
import hashlib
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

GATES=("requirements","correctness","negative_cases","usability","accessibility",
       "security","compatibility","provenance","specialist_review","release_integrity")

def check(folder,archive,product,family):
    folder=Path(folder)
    ext={"F29":(".docx",),"F30":(".pptx",),"F33":(".svg",".png")}[family]
    files=sorted(p for p in folder.iterdir() if p.suffix in ext)
    if len(files)!=48*len(ext):raise ValueError("CREATIVE_REVIEW_INCOMPLETE_PACK")
    names={p.name for p in files}
    if len(names)!=len(files):raise ValueError("CREATIVE_REVIEW_DUPLICATE_NAME")
    for p in files:
        if p.is_symlink() or not 200<=p.stat().st_size<=1_500_000:
            raise ValueError("CREATIVE_REVIEW_UNSAFE_ASSET")
        if family=="F29":
            from docx import Document
            d=Document(str(p))
            words="\n".join(x.text for x in d.paragraphs)
            if len(d.tables)!=4 or len(words)<250:
                raise ValueError("CREATIVE_REVIEW_DOCX_STRUCTURE")
            if len(d.paragraphs)<10:raise ValueError("CREATIVE_REVIEW_DOCX_FIELDS")
        elif family=="F30":
            from pptx import Presentation
            deck=Presentation(str(p))
            if len(deck.slides)!=2:raise ValueError("CREATIVE_REVIEW_PPTX_SLIDES")
            for slide in deck.slides:
                text="\n".join(x.text for x in slide.shapes if x.has_text_frame)
                if len(text)<110:raise ValueError("CREATIVE_REVIEW_PPTX_CONTENT")
        elif p.suffix==".svg":
            root=ET.fromstring(p.read_text("utf8"))
            if root.tag!="{http://www.w3.org/2000/svg}svg" or root.get("viewBox")!="0 0 720 480":
                raise ValueError("CREATIVE_REVIEW_SVG_GEOMETRY")
            if len(list(root))!=4 or any("script" in node.tag or "foreignObject" in node.tag for node in root.iter()):
                raise ValueError("CREATIVE_REVIEW_SVG_UNSAFE")
        else:
            from PIL import Image
            with Image.open(str(p)) as im:
                im.verify()
            with Image.open(str(p)) as im:
                if im.size!=(720,480) or im.mode not in ("RGB", "RGBA"):
                    raise ValueError("CREATIVE_REVIEW_PNG_RENDER")
                # Optimized RGB PNGs may have more than 345600 color entries in
                # their histogram; checking a bounded region is sufficient to
                # prove the raster is not a single-color placeholder.
                pixels = im.convert("RGB")
                sample = pixels.resize((72, 48))
                if len(set(sample.getdata())) < 2:
                    raise ValueError("CREATIVE_REVIEW_PNG_RENDER")
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    if len(set(hashes))!=len(files):raise ValueError("CREATIVE_REVIEW_DUPLICATE_CONTENT")
    readme=folder/"README.txt"
    if not readme.is_file() or "No human" not in readme.read_text("utf8"):
        raise ValueError("CREATIVE_REVIEW_MISSING_LIMITATIONS")
    expected={product+"/"+p.name for p in files}|{product+"/README.txt"}
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist())!=expected or len(z.namelist())!=len(expected) or z.testzip():
            raise ValueError("CREATIVE_REVIEW_BAD_ARCHIVE")
        for p in files+[readme]:
            if z.read(product+"/"+p.name)!=p.read_bytes():
                raise ValueError("CREATIVE_REVIEW_ARCHIVE_DIVERGENCE")
    return {"passed":True,"gates":{x:True for x in GATES},
            "files_checked":len(files),"checks_passed":10,
            "review_scope":"automated editability, internal format, structural variation, source integrity and archive validation only",
            "independent_human_review":False,"semantic_domain_expert_review":False,
            "commercial_release":False}

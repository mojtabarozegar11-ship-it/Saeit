#!/usr/bin/env python3
"""Build independently reversible static snapshots of 19 MojPlayWin editorial pages.

Exactly ten original illustrated notes per page. Reads original public HTML,
appends new sections without disturbing previous content, and generates
low-byte WebP thumbnails from images already in the project.
NO deployment, shared code edits, payments or child-site access in this script.
"""
from __future__ import annotations
import argparse,hashlib,html,json,re,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image,ImageOps

HERE=Path(__file__).resolve().parents[1]
DATA=HERE/"content/mojplaywin_ten_illustrated_articles_per_page_20261018.json"
IMAGES=HERE/"core/static/site/heroes"
PUBLIC="/design-preview-20261017/mpw-ten-editorials-20261018"
EXCLUDE={"/","/store/"}
MAX_BYTES=36000
INTRO=(
 "Start with a clearly defined purpose. In this field, {action}. Document assumptions before scaling a proposed approach.",
 "Evidence is more useful than sweeping claims. For this topic, {action}. Compare plausible alternatives before choosing a method.",
 "A professional explanation should be actionable: {action}. Describe where the model could fail or need additional data.",
 "Improvement begins with a small test, not a promise. The first step is to {action}. Record observations and revision criteria.",
 "Quality and safety belong inside the workflow. One essential practice is to {action}. Consider user needs and regulatory scope.",
 "Reliable work needs traceable information. To approach this question, {action}. Retain meaningful source dates and definitions.",
 "Make uncertainty visible rather than hiding it. In this subject, {action}. Invite informed review and documented corrections.",
 "Feasible implementation depends on constraints. A practical approach is to {action}. Compare benefits with cost and effort.",
 "Complex projects need clear ownership. The team should first {action}. Review dependencies before irreversible decisions.",
 "Long-term value requires accountability. For this subject, {action}. Explain the difference between prototype and verified output.",
)
ENDING=(
 "The immediate result should be {output}. This is a planning example, not evidence that any described service is currently operating.",
 "A useful output is {output}. Keep the review criteria visible so readers can independently assess the reasoning.",
 "Write the findings into {output}, stating what remains unverified and what would count as successful validation.",
 "The work should lead to {output}. Iterate using observed evidence and clearly identified failure conditions.",
 "Prepare {output}, with explicit assumptions and a credible route to real-world testing.",
 "A reader should take away {output}, traceable to the question and facts that motivated it.",
 "The next deliverable is {output}. Mark project ideas separately from facilities, products or services already confirmed.",
 "Assess the progress through {output}. Avoid interpreting a suggested process as proof of an operational installation.",
 "Capture the outcome in {output}, with responsibility for review and any necessary correction.",
 "Conclude with {output} and a clearly stated boundary between established knowledge and future development.",
)
STYLE="""<style id="mpw-ten-illustrated-style-20261018">
.mpw-ten-illustrated{box-sizing:border-box;max-width:1240px;margin:38px auto;padding:clamp(14px,3vw,30px);border-radius:20px;border:1px solid #b99751;background:linear-gradient(145deg,#141510,#090909);color:#f5f0e4;clear:both}
.mpw-ten-illustrated *{box-sizing:border-box}
.mpw-ten-illustrated .mpw-ten-eyebrow,.mpw-ten-illustrated .mpw-ten-index{letter-spacing:.12em;color:#debb75;font-size:.73rem;font-weight:800}
.mpw-ten-illustrated h2{font-size:clamp(1.5rem,3vw,2.5rem);line-height:1.22;color:#f5e9d1;margin:9px 0 15px}
.mpw-ten-illustrated .mpw-ten-lead{color:#d4cabc;max-width:90ch;line-height:1.8;font-size:1rem}
.mpw-ten-illustrated .mpw-ten-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px;margin-top:23px}
.mpw-ten-illustrated .mpw-ten-card{background:#171712;border:1px solid rgba(215,183,104,.35);border-radius:14px;overflow:hidden;min-width:0}
.mpw-ten-illustrated .mpw-ten-card img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border:0}
.mpw-ten-illustrated .mpw-ten-copy{padding:clamp(13px,2vw,22px)}
.mpw-ten-illustrated h3{font-size:clamp(1.05rem,1.6vw,1.38rem);line-height:1.3;margin:9px 0;color:#f4e7c7}
.mpw-ten-illustrated .mpw-ten-copy p{font-size:.95rem;line-height:1.76;color:#dad1c4;margin:8px 0 13px;overflow-wrap:anywhere}
@media(max-width:700px){.mpw-ten-illustrated{margin:22px auto;padding:12px;border-radius:12px}.mpw-ten-illustrated .mpw-ten-grid{grid-template-columns:1fr;gap:12px}}
@media(prefers-reduced-motion:reduce){.mpw-ten-illustrated *{animation:none!important;transition:none!important}}
</style>"""
class PageParser(HTMLParser):
    def __init__(self):super().__init__();self.mains=0;self.forms=0;self.submit=0
    def handle_starttag(self,name,attrs):
        a=dict(attrs)
        if name=="main":self.mains+=1
        if name=="form":self.forms+=1
        if name=="button" and a.get("type")=="submit":self.submit+=1

def slug(path):return "root" if path=="/" else "-".join(x for x in path.strip("/").split("/") if x)
def guard(source,path):
    parsed=PageParser();parsed.feed(source)
    if parsed.mains!=1 or len(re.findall(r"</main\s*>",source,re.I))!=1:raise ValueError("Main landmark mismatch "+path)
    if parsed.forms or parsed.submit:raise ValueError("Live interactive form, refuse static copy: "+path)
    if 'mpw-ten-illustrated-20261018' in source:raise ValueError("Already published "+path)
    if re.search(r'payment[-_]?gateway|crypto_checkout|checkout_session|payment-form',source,re.I):raise ValueError("Potential checkout "+path)
    if "<!doctype" not in source.lower() or not 300<len(source)<900000:raise ValueError("Unsafe HTML source")

def articles(data,path):
    info=data["pages"][path]
    if len(info["items"])!=10:raise ValueError("Wrong article count")
    s=slug(path)
    nodes=[f'<section id="mpw-ten-illustrated-20261018" class="mpw-ten-illustrated" aria-labelledby="mpw-ten-heading-{s}">',
       '<p class="mpw-ten-eyebrow">MOJPLAYWIN · TEN VISUAL FIELD NOTES</p>',
       f'<h2 id="mpw-ten-heading-{s}">Ten illustrated guides: {html.escape(info["title"])}</h2>',
       '<p class="mpw-ten-lead">Ten independent educational notes, each with a practical method and a lightweight image. Described capabilities are not automatically evidence of live products or licensed operations.</p>',
       '<div class="mpw-ten-grid">']
    for idx,item in enumerate(info["items"]):
        title=html.escape(item["title"])
        first=html.escape(INTRO[idx].format(action=item["method"]))
        second=html.escape(ENDING[idx].format(output=item["deliverable"]))
        if len(first)+len(second)<160:raise ValueError("Editorial item too short")
        image=f"{PUBLIC}/images/{s}-{idx+1:02d}.webp"
        alt=html.escape(item["title"]+" — MojPlayWin specialist illustration",quote=True)
        nodes.append(f'<article class="mpw-ten-card" id="mpw-note-{s}-{idx+1:02d}">'
            f'<img src="{image}" alt="{alt}" width="420" height="236" loading="lazy" decoding="async">'
            f'<div class="mpw-ten-copy"><span class="mpw-ten-index">FIELD NOTE {idx+1:02d}</span>'
            f'<h3>{title}</h3><p>{first}</p><p>{second}</p></div></article>')
    nodes.append('</div></section>')
    return "\n".join(nodes)

def render(existing,data,path):
    guard(existing,path)
    if existing.count("</head>")!=1:raise ValueError("No unique head")
    h=existing.replace("</main>",articles(data,path)+"\n</main>",1)
    h=h.replace("</head>",STYLE+"\n</head>",1)
    if h.count('class="mpw-ten-card"')!=10 or h.count('id="mpw-ten-illustrated-20261018"')!=1:
        raise ValueError("New article count mismatch")
    return h

def assets(data,paths,output):
    folder=output/"images";folder.mkdir()
    base="research ai knowledge education-detail industry economy game-studio marketplace services agriculture store laboratory smart-agriculture genetics weather academy platform-home blog newsletter auctions contact".split()
    records={}
    for path in paths:
        images=list(dict.fromkeys(data["pages"][path]["images"]+base))
        records[path]=[]
        for i,stem in enumerate(images[:10]):
            inp=IMAGES/(stem+".webp")
            if not inp.is_file():raise ValueError("Source photo absent: "+stem)
            with Image.open(inp) as raw:
                bias=(.36+((len(slug(path))+i*7)%27)/100,.36+((len(slug(path))+i*11)%27)/100)
                pic=ImageOps.fit(raw.convert("RGB"),(420,236),method=Image.Resampling.LANCZOS,centering=bias)
                dst=folder/(slug(path)+f"-{i+1:02d}.webp")
                for q in (52,42,32,22):
                    pic.save(dst,format="WEBP",quality=q,method=6)
                    if dst.stat().st_size<=MAX_BYTES:break
                if dst.stat().st_size>MAX_BYTES:raise ValueError("Oversized WebP "+dst.name)
                records[path].append({"file":"images/"+dst.name,"bytes":dst.stat().st_size,
                                      "sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),
                                      "source":inp.name})
    return records

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--output",required=True)
    cli.add_argument("--paths",nargs="+")
    cli.add_argument("--public",action="store_true")
    cli.add_argument("--input-dir")
    opts=cli.parse_args()
    data=json.loads(DATA.read_text("utf-8"))
    paths=opts.paths or [x for x in data["pages"] if x not in EXCLUDE]
    if len(paths)!=len(set(paths)) or any(x not in data["pages"] or x in EXCLUDE for x in paths):raise ValueError("Unsafe route list")
    out=Path(opts.output)
    out.mkdir(parents=True,exist_ok=False)
    (out/"pages").mkdir()
    manifest={}
    for path in paths:
        if opts.public:
            req=urllib.request.Request("https://mojplaywin.com"+path+"?__mpw_content_snapshot=20261018",
                    headers={"User-Agent":"MojPlayWinVisualEditorialBuild/1.0","Cache-Control":"no-cache"})
            with urllib.request.urlopen(req,timeout=24) as r:
                if r.status!=200 or "text/html" not in r.headers.get("Content-Type",""):raise ValueError("Source HTTP invalid "+path)
                source=r.read(900001).decode("utf-8","replace")
        else:
            if not opts.input_dir:raise ValueError("Require input-dir or public")
            source=(Path(opts.input_dir)/(slug(path)+".html")).read_text("utf-8")
        result=render(source,data,path)
        dest=out/"pages"/(slug(path)+".html")
        dest.write_text(result,"utf-8")
        manifest[path]={"file":"pages/"+dest.name,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),
                        "bytes":dest.stat().st_size,"articles":10,"preserves_original":True}
        print("EDITORIAL_PAGE_READY="+json.dumps({"path":path,**manifest[path]}),flush=True)
    pics=assets(data,paths,out)
    (out/"manifest.json").write_text(json.dumps({"version":"2026-10-18","paths":manifest,"images":pics,"excluded":["/","/store/"],
        "images_max_bytes":MAX_BYTES,"domain":"mojplaywin.com","editorial_only":True},indent=2),"utf-8")
    print("EDITORIAL_ILLUSTRATED_BUILD_PASS="+json.dumps({"paths":len(paths),"articles":len(paths)*10,"images":sum(map(len,pics.values()))}),flush=True)
if __name__=="__main__":main()

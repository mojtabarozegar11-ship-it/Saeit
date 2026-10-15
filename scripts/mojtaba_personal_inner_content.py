#!/usr/bin/env python3
"""Fill existing V17 personal pages conservatively; keep database-driven content intact.

Scope: eight specific templates. No changes to routing, base, media, payments, or other sites.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
BASE = "templates/personal_site/core"
PHOTO_STATIC = "{% static 'personal_site/owner_gallery_20261015/photo-%02d.jpg' %}"
MARK = 'id="mpw-inner-content-20261015"'
EXPECTED = {
    "about": "ec21a4eb388eb9390d57d85a3118ef0a08069a4258f37f4f6474fd55145a20d3",
    "projects": "e7edc45142dd16e4b964861e01d97facf114d3bcea7635746701bb6e8a052bfd",
    "posts": "fc4d0d39ba98d2bbd2735c3988bed05d365c99085f4dd2f480369c139e3c2111",
    "gallery": "c87859be0ef0586a59bc4bc9eec2b7bdd215eef757ef48b95c55cc3ceb0d22be",
    "resume": "1f0b9a44ee4d5c282306f46b5e6f2fffb58485a9d22faaf7eed0497f4ea5857f",
    "activities": "09293d61ec41c1e728a15d9acd9a507a0a5cbc898fd04e515cdd1b80180808b6",
    "memories": "d619ac32fb9ab5d4d59915c7e5745e78706182e1fa9339e64794ff519813611c",
    "stories": "69a2c3e85175b64fe976f5ccee8f0010be612946052fccb0b9b94b304d9d52f2",
}
DESCRIPTIONS = {
 "projects": "Explore Mojtaba Roozegar's professional background and the development directions of MojPlayWin, agribusiness, research, education and digital projects.",
 "posts": "Read research-minded essays on science, technology, agricultural economics, entrepreneurship, digital products and education from Mojtaba Roozegar's personal site.",
 "gallery": "Browse ten individually presented Mojtaba Roozegar branded editorial portraits featuring MojPlayWin, Zomorod Melal, leadership and agricultural innovation.",
 "resume": "Professional experience of Mojtaba Roozegar across agribusiness leadership, jewelry, precious metals, carpets, hospitality, research and website development.",
 "activities": "Professional areas, activities and interests of Mojtaba Roozegar, from agricultural economics and business development to scientific writing and technology.",
 "memories": "Personal reflections by Mojtaba Roozegar on Iranian cultural heritage, an unexpected move abroad and the meaning of professional reinvention.",
 "stories": "A clearly labelled fictional vignette and reflections on creative storytelling, distinct from the factual personal history of Mojtaba Roozegar.",
}
TITLES = {
"about":"About Mojtaba Roozegar | Founder, Researcher & Entrepreneur",
"projects":"Projects & Initiatives | Mojtaba Roozegar",
"posts":"Research Notes & Journal | Mojtaba Roozegar",
"gallery":"Personal Photo Gallery | Mojtaba Roozegar",
"resume":"Experience & Career | Mojtaba Roozegar",
"activities":"Work & Activities | Mojtaba Roozegar",
"memories":"Personal Journey | Mojtaba Roozegar",
"stories":"Original Fiction | Mojtaba Roozegar",
}
CSS = """<style>
.mpw-inner{grid-column:1/-1;width:100%;max-width:1180px;margin:0 auto;padding:25px 0 38px;color:#1a2b3d;box-sizing:border-box}
.mpw-inner *{box-sizing:border-box}
.mpw-inner h2{font:normal clamp(28px,4vw,46px)/1.18 Georgia,'Times New Roman',serif;color:#1b2939;margin:8px 0 22px}
.mpw-inner h3{font:normal clamp(21px,2.5vw,29px)/1.23 Georgia,'Times New Roman',serif;color:#182a3a;margin:0 0 10px}
.mpw-inner p{font-size:clamp(15px,1.55vw,18px);line-height:1.82;margin:0 0 16px;color:#445362}
.mpw-inner .mpw-kicker{color:#80622c;font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:800}
.mpw-inner .mpw-intro{max-width:870px;margin-bottom:24px}
.mpw-inner .mpw-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:23px}
.mpw-inner .mpw-cards.mpw-three{grid-template-columns:repeat(3,minmax(0,1fr))}
.mpw-inner .mpw-card{border:1px solid #ded5c6;border-radius:8px;overflow:hidden;background:#fff;box-shadow:0 7px 24px rgba(20,35,50,.055)}
.mpw-inner .mpw-card img{width:100%;height:285px;object-fit:cover;display:block;background:#182837}
.mpw-inner .mpw-card .mpw-copy{padding:22px}
.mpw-inner .mpw-card .mpw-copy p{font-size:16px}
.mpw-inner .mpw-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:17px}
.mpw-inner figure{margin:0}
.mpw-inner .mpw-gallery figure{background:#132437;border:1px solid #b5a17d;border-radius:8px;overflow:hidden}
.mpw-inner .mpw-gallery img{width:100%;height:285px;object-fit:contain;display:block}
.mpw-inner figcaption{padding:14px 17px;color:#e7dfd0;font-size:13px;line-height:1.55}
.mpw-inner figcaption strong{display:block;color:#fff;font-size:14px;margin-bottom:3px}
.mpw-inner .mpw-essay{padding:28px;background:#fff;border:1px solid #ded5c6;border-radius:8px;margin:0 0 19px}
.mpw-inner .mpw-essay summary{font:normal 25px/1.3 Georgia,'Times New Roman',serif;cursor:pointer;color:#1b2b3d}
.mpw-inner .mpw-essay summary:focus-visible{outline:3px solid #b99863}
.mpw-inner .mpw-essay img{float:right;max-width:36%;height:auto;max-height:350px;object-fit:cover;margin:5px 0 10px 23px;border-radius:5px}
.mpw-inner .mpw-essay p{font-size:16px}
.mpw-inner .mpw-essay p:first-of-type{margin-top:20px}
.mpw-inner .mpw-callout{margin-top:25px;background:#14283b;color:#e8d6b8;padding:24px 28px;border-left:4px solid #cda86a}
.mpw-inner .mpw-callout p,.mpw-inner .mpw-callout a{color:#f0e7d8}
.mpw-inner .mpw-journey{padding:25px;background:#fff;border-left:4px solid #be9a60;margin-bottom:19px}
.mpw-inner .mpw-journey span{color:#86662f;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.1em}
.mpw-inner .mpw-journey p{margin-top:9px}
.mpw-inner .mpw-note{font-size:13px;color:#586577;margin-top:18px}
@media(max-width:880px){.mpw-inner .mpw-cards.mpw-three{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.mpw-inner{padding:12px 0 25px}.mpw-inner .mpw-cards,.mpw-inner .mpw-cards.mpw-three{grid-template-columns:1fr}.mpw-inner .mpw-gallery{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.mpw-inner .mpw-gallery img{height:190px}.mpw-inner figcaption{padding:11px}.mpw-inner .mpw-essay img{float:none;max-width:100%;max-height:none;width:100%;height:230px;margin:16px 0}.mpw-inner .mpw-essay{padding:19px}}
</style>"""
def img(i:int,alt:str)->str:
    return '<img src="'+PHOTO_STATIC%i+'" alt="'+html.escape(alt,quote=True)+'" loading="lazy" decoding="async">'
def card(i:int,title:str,text:str,label:str="PROFESSIONAL FOCUS")->str:
    return '<article class="mpw-card">'+img(i,title+' — supplied editorial portrait')+'<div class="mpw-copy"><span class="mpw-kicker">'+label+'</span><h3>'+title+'</h3><p>'+text+'</p></div></article>'
def wrapper(title:str,intro:str,body:str,sub:str="INSIDE THE STORY")->str:
    return '<div id="mpw-inner-content-20261015" class="mpw-inner">'+CSS+'<span class="mpw-kicker">'+sub+'</span><h2>'+title+'</h2><p class="mpw-intro">'+intro+'</p>'+body+'</div>'
def grid(*cards:str, three:bool=False)->str:
    return '<div class="mpw-cards'+(' mpw-three' if three else '')+'">'+"".join(cards)+'</div>'
def callout(text:str)->str:
    return '<div class="mpw-callout"><p>'+text+'</p></div>'
def about()->str:
    body=grid(
        card(1,"The MojPlayWin chapter","I founded MojPlayWin as a place to explore science, AI, digital products, gaming and education. Its focus is intended to be 80% future-facing research and technology, with 20% drawing on my earlier business experience.","CURRENT DIRECTION"),
        card(6,"Years of practical experience","My background includes leading Zomorod Melal Agro-Industry Company and work in agricultural planning, trade, jewelry, carpets, hospitality, research and professional web development.","PROFESSIONAL BACKGROUND"),
        card(9,"Culture and personal identity","I carry the heritage of Iran, the land of Cyrus the Great and Persepolis, into a new chapter abroad. An unexpected move has changed my circumstances, not the value of what I have learned.","PERSONAL JOURNEY"),
        card(5,"An invitation to collaborate","This website is a bridge to people in Canada and internationally who value useful research, responsible entrepreneurship and practical cooperation. Please get in touch through the existing contact page.","GET IN TOUCH")
    )
    return wrapper("A personal story across borders.","An Iranian perspective, experience across several industries, and a new professional beginning in Vancouver.",body,"MEET MOJTABA ROOZEGAR")
def projects()->str:
    body=grid(
        card(2,"Zomorod Melal — agribusiness leadership","Professional background in agricultural business administration, scientific project oversight and multidisciplinary operations. This is a description of experience, not a claim of a newly delivered Canadian project.","PROFESSIONAL EXPERIENCE"),
        card(1,"MojPlayWin — digital business direction","The planned platform brings together research-driven digital products, gaming, AI and education. Features and products should be evaluated on their individual readiness before being called commercially available.","FOUNDER VISION"),
        card(4,"Agricultural economics and practical tools","An area for research into land, water, production costs and decisions under uncertainty. The goal is to turn rigorous analysis into understandable and useful decision support.","RESEARCH DIRECTION"),
        card(3,"Education, publishing and games","An intended pipeline for learning resources, original interactive work and professional publications. Works will be identified individually as planned, in development or released as they become verifiable.","DEVELOPMENT DIRECTION")
    )
    return wrapper("Experience, initiatives and ideas.","A portfolio does not need inflated claims. These are established fields of experience alongside transparent directions for future products and collaboration.",body)
def essay(i:int,title:str,paras:list[str],label:str)->str:
    return '<details class="mpw-essay" open><summary>'+title+'</summary><p class="mpw-kicker">'+label+'</p>'+img(i,title+' — editorial image')+''.join('<p>'+p+'</p>' for p in paras)+'<div style="clear:both"></div></details>'
def posts()->str:
    body=(
       essay(4,"How to evaluate agricultural decisions under water scarcity",[
          "A useful farm decision begins with a clear unit of analysis: a field, a crop, a season or an entire enterprise. For each alternative, estimate expected yield, selling price, variable cost, labor requirements, water use and the uncertainty of each assumption. Gross margin can inform comparison, but it is not the same as net profit or cash available to the owner.",
          "When water is limiting, ranking crops only by revenue per hectare can be misleading. Consider contribution per cubic meter of irrigation water, minimum operational requirements and the opportunity cost of using scarce water for one crop instead of another. A plan must also account for crop rotations, market constraints and soil health.",
          "Finally, test more than one scenario. Lower yields, changes in input prices or a short period of drought can reverse the apparent ranking. Write assumptions next to each result, document the source of measurements and revisit recommendations when evidence changes. This is a decision framework, not a farm-specific prescription."
       ],"AGRICULTURAL ECONOMICS · PRACTICAL RESEARCH NOTE"),
       essay(3,"From a promising idea to a credible digital product",[
          "A professional digital product starts with a defined audience and a problem important enough to solve. Before adding complex features, write a precise promise: what decision, task or learning outcome should improve for a user? That promise is testable and becomes the basis for product design.",
          "Build a small working version, validate it using representative tasks, and record both failures and success rates. Quality includes accuracy, accessibility, speed, security and clarity of documentation. A polished interface cannot rescue unclear content or a broken purchase and delivery path.",
          "Commercial readiness deserves a separate checklist: rights to the included material, a fair price, reliable access, support expectations and the ability to deliver what is advertised. Avoid treating internal automated tests as proof that real customers have completed a purchase. Publish evidence and limitations alongside meaningful benefits."
       ],"TECHNOLOGY · PRODUCT DEVELOPMENT NOTE"),
       essay(8,"Research, games and education: one connected approach",[
          "Good learning and good game design share a foundation: clear goals, feedback, meaningful progression and choices that matter. A learner should understand what is being practiced, while a player should understand how an action changes the experience. Both benefit from careful iteration.",
          "Scientific thinking adds discipline. Form a question, identify a measurable outcome, compare alternatives and remain open to being wrong. For educational products, test whether people can actually apply the knowledge rather than simply remember an attractive presentation.",
          "The MojPlayWin direction brings these disciplines together. It is a roadmap for research-led digital work, not a claim that every proposed game or course has already shipped. Responsible communication keeps the difference visible while the work develops."
       ],"RESEARCH · GAME DESIGN · EDUCATION")
    )
    return wrapper("Ideas explained, not merely announced.","Three substantial editorial research notes on agricultural economics, responsible product development and learning through interactive systems. These are educational frameworks rather than peer-reviewed empirical findings.",body,"RESEARCH NOTES & JOURNAL")
def gallery()->str:
    titles=["MojPlayWin founder portrait","Zomorod Melal — desk and digital work","Business presentation","Agricultural innovation discussion","Professional partnership","Executive portrait","Zomorod Melal leadership portrait","MojPlayWin close-up portrait","MojPlayWin formal portrait","Agribusiness leadership portrait"]
    body='<div class="mpw-gallery">'+''.join('<figure><a href="'+PHOTO_STATIC%i+'" target="_blank" rel="noopener" aria-label="View image '+str(i)+'">'+img(i,t)+'</a><figcaption><strong>'+f"{i:02}"+' / '+t+'</strong>Owner-supplied branded editorial image</figcaption></figure>' for i,t in enumerate(titles,1))+'</div>'
    return wrapper("Ten distinct images, one professional narrative.","Browse the complete supplied collection individually. Each image remains unaltered and can be opened separately; the scenes are illustrative and are not independent evidence of specific meetings or office locations.",body,"THE ORIGINAL IMAGE COLLECTION")
def resume()->str:
    entries=[
       ("Company management — Zomorod Melal","Agribusiness, production planning and operational management are central to my professional background in Iran. Responsibilities include coordinating people, projects and commercial decisions."),
       ("Scientific research and writing","My interests include applied agricultural economics, research methods, business analysis, scientific writing and making technical knowledge accessible to different audiences."),
       ("Jewelry, precious metals and carpets","Experience across jewelry management, gold coin commerce and specialist carpet trading has informed my understanding of craftsmanship, product value and customer relationships."),
       ("Hospitality and customer operations","Café and restaurant management develops practical skills in service quality, staffing, purchasing, workflow organization and decision-making under daily operational pressure."),
       ("Digital development","Building professional websites connects design and information architecture with content, technical maintenance, digital communication and reliable user experiences."),
       ("MojPlayWin — new business chapter","In Vancouver, the intended priority is scientific research, AI, modern digital technology, original games and education, while continuing selected collaboration based on earlier experience.")
    ]
    body=''.join('<article class="mpw-journey"><span>EXPERIENCE AREA '+f"{i:02}"+'</span><h3>'+a+'</h3><p>'+b+'</p></article>' for i,(a,b) in enumerate(entries,1))
    body+=callout('This profile presents areas of professional experience rather than invented employment dates, credentials or project outcomes. <a href="{% url \'personal_site:contact\' %}">Contact me</a> for relevant details.')
    return wrapper("A multidisciplinary professional path.","Agriculture, research, business leadership, trading, hospitality and technology have shaped the way I approach new ventures.",body,"CAREER & EXPERIENCE")
def activities()->str:
    body=grid(
        card(4,"Agriculture and scientific projects","Applied production economics, agricultural analysis and the management of research or operational initiatives form one key part of my experience."),
        card(3,"Research communication and teaching","I am interested in translating complex subjects into structured explanations, learning materials and professionally useful resources."),
        card(5,"Trade and business operations","Experiences involving jewelry, coins, carpets and hospitality contribute practical knowledge about products, value, business processes and client service."),
        card(2,"Technology and web development","A continuing direction includes digital products, professional websites, AI-supported research, creative tools, gaming and education.")
    )
    return wrapper("Work through many disciplines.","The strongest connections emerge where business practice meets curiosity, evidence and technology. These are areas of professional work and interest, not invented dated assignments.",body)
def memories()->str:
    body='<div class="mpw-journey"><span>REFLECTION · ROOTS</span><h3>What I carry from Iran</h3><p>I am Iranian and proud of the culture and history associated with the land of Cyrus and Persepolis. That background remains part of my identity, no matter where I work or live.</p><p>In my professional life in Iran, I encountered people, industries and disciplines that demanded different skills. Those experiences remain valuable precisely because they were varied: from agriculture and management to research and trade.</p></div>'
    body+='<div class="mpw-journey"><span>REFLECTION · A NEW CHAPTER</span><h3>An unexpected move to Vancouver</h3><p>My relocation to Vancouver, British Columbia, was involuntary, unexpected and unplanned. I do not want to invent precise dates, routes or private events simply to make the story more dramatic.</p><p>Instead, this page shares the part I am ready to make public: the experience of starting again, carrying knowledge forward and seeking connections through MojPlayWin.</p></div>'
    body+=callout("These reflections follow my own publicly supplied introduction; additional dated memories can be published separately when their details are provided.")
    return wrapper("The journey behind the work.","Not every meaningful experience needs a fictional timeline. This section begins with the cultural roots and life transition I have chosen to share.",body,"PERSONAL REFLECTIONS")
def stories()->str:
    body='<article class="mpw-essay"><span class="mpw-kicker">FICTIONAL VIGNETTE · EDITORIAL SAMPLE</span><h3>The Workshop of Unfinished Maps</h3>'
    body+='<p>At the edge of an unfamiliar city, a maker rented a workshop whose windows faced a harbor. He arrived with an empty desk, a worn notebook and a wooden box of tools that had crossed many borders.</p>'
    body+='<p>Each morning, he drew a map of something that did not yet exist: a school where questions were worth more than answers, a game whose players learned to cooperate, or a garden where every seed carried a small piece of history.</p>'
    body+='<p>A visitor asked why none of the maps had a final destination. The maker smiled. “Because a destination can be mistaken. A direction can be tested.” He unrolled the newest sheet, left a space for the visitor to draw and offered a pencil.</p>'
    body+='<p>Years later, the harbor had changed and the workshop had more than one door. The maps were still unfinished. But the people who helped draw them had already built a place where strangers could work together.</p></article>'
    body+=callout("This short story is fictional editorial writing created for this page. Its people and events should not be interpreted as the founder's personal memories or verified biography.")
    return wrapper("A place for imagination.","An original fictional sample, clearly separated from personal biography and professional reporting.",body,"IMAGINATION · FICTION")
BUILDERS={"about":about,"projects":projects,"posts":posts,"gallery":gallery,"resume":resume,"activities":activities,"memories":memories,"stories":stories}

def patch(name:str,source:str)->str:
    if MARK in source: raise ValueError("Already patched "+name)
    if "{% block content %}" not in source or "{% endblock %}" not in source: raise ValueError("Unexpected Django template")
    if name == "about":
        # Replace dated, inconsistent and potentially database-overridden biography with owner-provided narrative.
        start=source.find('<div class="prose">')
        end=source.find('</div><a class="btn btn-dark"',start)
        if start<0 or end<0: raise ValueError("About prose anchor missing")
        new_prose=('<div class="prose"><p>I am Mojtaba Roozegar, an entrepreneur and researcher from Iran, '
                   'now based in Vancouver, British Columbia, Canada. I founded MojPlayWin to connect '
                   'research, innovation, digital technology, games and education with international collaboration.</p>'
                   '<p>My previous experience includes serving as CEO of Zomorod Melal Agro-Industry Company, '
                   'managing agricultural and scientific projects, and professional work in jewelry, gold coins, '
                   'carpet trading, hospitality, research, writing and website development.</p>'
                   '<p>My move to Canada was unexpected and not part of my original plans. I remain proud of '
                   'my Iranian heritage and want this website to be a bridge for meaningful ideas and '
                   'professional cooperation across borders.</p>'
                   '<p>The intended MojPlayWin direction is 80% scientific research, modern technologies, '
                   'gaming and education, and 20% selected collaboration drawing on my earlier industries.</p>')
        source=source[:start]+new_prose+source[end:]
    else:
        needle="{% empty %}"
        endmark="{% endfor %}"
        if source.count(needle)!=1 or source.count(endmark)!=1:
            raise ValueError("Expected exactly one empty-list fallback in "+name)
        start=source.index(needle)+len(needle)
        end=source.index(endmark,start)
        source=source[:start]+BUILDERS[name]()+source[end:]
    if name == "about":
        # About has no DB-driven list. Insert finished content after its existing biography.
        close=source.rfind("{% endblock %}")
        source=source[:close]+'<section class="section section-cream"><div class="shell">'+BUILDERS[name]()+'</div></section>\n'+source[close:]
    elif "{% load static %}" not in source:
        source=source.replace("{% extends 'personal_site/base.html' %}","{% extends 'personal_site/base.html' %}{% load static %}",1)
    if name!="about":
        title_re=r"{%\s*block title\s*%}.*?{%\s*endblock\s*%}"
        source,count=re.subn(title_re,"{% block title %}"+TITLES[name]+"{% endblock %}",source,count=1,flags=re.S)
        if count!=1: raise ValueError("Title block mismatch")
        source=source.replace("{% block content %}","{% block description %}"+DESCRIPTIONS[name]+"{% endblock %}\n{% block content %}",1)
    else:
        source=source.replace("{% block title %}About — Mojtaba Roozegar{% endblock %}","{% block title %}"+TITLES[name]+"{% endblock %}",1)
    if source.count(MARK)!=1: raise ValueError("Exactly one content marker required")
    if name == "gallery" and source.count("owner_gallery_20261015/photo-")!=20: raise ValueError("Ten gallery original source references required")
    return source

def read_state(app:Path,expected:bool=True)->dict[str,str]:
    result={}
    for name,digest in EXPECTED.items():
        f=app/BASE/(name+".html")
        if f.is_symlink() or not f.is_file() or f.resolve()!=f: raise ValueError("Unsafe template "+name)
        text=f.read_text(encoding="utf-8")
        if expected and hashlib.sha256(text.encode()).hexdigest()!=digest:
            raise ValueError("Template changed since read-only audit: "+name)
        result[name]=text
    return result

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("check","install","rollback"))
    parser.add_argument("--backup-dir",type=Path,required=True)
    args=parser.parse_args()
    app=APP
    if not app.is_dir() or app.is_symlink() or not (app/"manage.py").is_file():
        raise SystemExit("V17 personal Django installation not verified")
    backup=args.backup_dir
    if args.mode=="rollback":
        if not backup.is_dir() or backup.is_symlink(): raise SystemExit("Backup directory not found")
        for name in EXPECTED:
            b=backup/(name+".html")
            f=app/BASE/(name+".html")
            if not b.is_file(): raise SystemExit("Backup incomplete: "+name)
            tmp=f.with_name(f.name+".restore-temp")
            shutil.copy2(b,tmp)
            os.replace(tmp,f)
        restart=app/"tmp/restart.txt"
        if restart.parent.is_dir():restart.touch()
        print("ROLLBACK_TEMPLATES=8")
        return
    current=read_state(app)
    static_dir=app/"static/personal_site/owner_gallery_20261015"
    for i in range(1,11):
        if not (static_dir/("photo-%02d.jpg"%i)).is_file(): raise SystemExit("Missing previously deployed photo "+str(i))
    modified={name:patch(name,data) for name,data in current.items()}
    print("PRECHECK_ORIGINAL_TEMPLATES=8")
    print("GALLERY_STATIC_SOURCE=10")
    print("CONTENT_PAGES_PREPARED=8")
    if args.mode=="check": return
    if backup.exists():raise SystemExit("Backup destination already exists")
    backup.mkdir(parents=True,mode=0o700)
    for name,data in current.items():
        b=backup/(name+".html")
        b.write_text(data,encoding="utf-8")
        b.chmod(0o600)
    if len(list(backup.glob("*.html")))!=8:raise SystemExit("Backup incomplete")
    changed=[]
    try:
        for name,new in modified.items():
            f=app/BASE/(name+".html")
            tmp=f.with_name(f.name+".inner-tmp")
            tmp.write_text(new,encoding="utf-8")
            os.chmod(tmp,f.stat().st_mode & 0o777)
            os.replace(tmp,f)
            changed.append(name)
    except BaseException:
        for name in changed:
            f=app/BASE/(name+".html")
            shutil.copy2(backup/(name+".html"),f)
        raise
    restart=app/"tmp/restart.txt"
    if restart.parent.is_dir():restart.touch()
    print("EIGHT_TEMPLATES_INSTALLED=yes")
    print("BACKUP_PATH="+str(backup))

if __name__=="__main__":
    main()

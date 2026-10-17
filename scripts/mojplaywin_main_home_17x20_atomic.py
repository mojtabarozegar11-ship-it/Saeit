#!/usr/bin/env python3
"""Rebuild ONLY the already-live MojPlayWin main homepage's THREE orbit rows into
17 genuine interactive rows, each with EXACTLY 20 distinct cards (340 total).

Existing 18 photo cards kept byte-for-byte and in original order. Other 322
cards use unique CSS-only abstract visuals (NO duplicated images).
No child routes/files, Passenger, commerce, DB, checkout, WSGI, .htaccess edits.
Exact SHA preimage and verified private backup; atomic install and rollback.
"""
from __future__ import annotations
import hashlib, html, json, os, re, subprocess, sys
from pathlib import Path
ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/production-home-20261017.html"
HT=ROOT/".htaccess"
BACKROOT=Path("/home/zomorod2/.mpw-17x20-mainonly-backups")
EXPECTED_SHA="dc027fa3d96644d26d4c1d0ee7b77d9d54b8a3e79c430c1d8ed47a08e1e2ae00"
HT_SHA="5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
MARKER='id="mpw-17x20-mainonly-style"'
ROWS=json.loads(r'''[{"slug":"web","title":"Web Engineering","focus":"Web systems, accessible interfaces and responsible deployment","url":"/services/","topics":["UX research","Responsive layouts","Django architecture","Secure authentication","Payment integration planning","Multi-language design","Web accessibility","Performance profiling","API orchestration","Design systems","Search-friendly structure","Forms and validation","Database migration planning","Web reliability","Infrastructure diagrams","Quality assurance","Automated release testing","Content governance","Client handover","Site maintenance"]},{"slug":"digital","title":"Digital Innovation","focus":"Real-world digital products, education and creative research","url":"/research/","topics":["Game prototyping","Human-centered AI","Digital books","Applied research","Blockchain foundations","Knowledge platforms","Creative coding","Privacy-aware analytics","Digital onboarding","Machine learning evaluation","Interactive learning","Cross-device usability","Digital inclusion","Research dashboards","Workflow assistants","Audio-visual storytelling","Product discovery","Experiment design","Open standards","Innovation roadmaps"]},{"slug":"ventures","title":"Connected Ventures","focus":"Domain expertise, feasible service models and documented operations","url":"/company/","topics":["Farm enterprise planning","Restaurant operations","Jewelry documentation","Carpet provenance","Hotel guest experience","Digital commerce","Fuel station feasibility","Rural production systems","Customer journey mapping","Supply chain traceability","Regional market analysis","Cost and margin modeling","Small business automation","Craft product photography planning","Service quality measurement","Vendor compliance","Resource efficiency","Client proposals","Digital storefront readiness","Partnership due diligence"]},{"slug":"games","title":"Original Games & Interaction","focus":"Original game design, player learning and interactive experiences","url":"/studio/","topics":["Game mechanics","Puzzle progression","Player feedback","Interactive storytelling","Level balancing","Touch controls","Browser game performance","Game accessibility","Scoring systems","Cooperative play concepts","Original art direction","Prototype validation","Player onboarding","Learning through play","Non-exploitative rewards","Multiplayer architecture","Replay value","Game analytics ethics","QA playtests","Release documentation"]},{"slug":"ai","title":"Artificial Intelligence","focus":"Human-supervised intelligence and practical automation workflows","url":"/ai/","topics":["Prompt evaluation","Data quality","Retrieval pipelines","Document classification","Model monitoring","Bias checks","Human review steps","AI tutoring aids","Research summarization","Workflow routing","Tool permissions","Grounded responses","AI-assisted coding","Dataset governance","Error recovery","Audit logs","Cost estimation","Security boundaries","Multilingual assistants","Deployment risk review"]},{"slug":"research","title":"Scientific Research","focus":"Transparent methodology, reproducible evidence and careful reporting","url":"/research/","topics":["Research question design","Literature synthesis","Sampling strategy","Data collection plans","Experimental controls","Field measurement","Qualitative coding","Statistical assumptions","Sensitivity analysis","Peer review checklist","Reproducibility records","Ethical considerations","Uncertainty reporting","Evidence grading","Research visualization","Citation verification","Applied prototypes","Replication planning","Scientific writing","Method limitations"]},{"slug":"knowledge","title":"Academy & Learning","focus":"Learning resources, guided study and professional knowledge","url":"/knowledge/","topics":["Learning objectives","Course outlines","Practical exercises","Assessment rubrics","Evidence-based lessons","Reading pathways","Visual explanations","Knowledge maps","Multilingual learning","Digital worksheets","Worked examples","Reference curation","Accessibility of lessons","Skills validation","Learner support","Feedback loops","Curriculum sequencing","Academic integrity","Learning analytics privacy","Continuing education"]},{"slug":"products","title":"Digital Products & Publishing","focus":"Well-scoped informational products and reliable buyer experiences","url":"/store/","topics":["Ebook structure","Workbook design","Template packaging","File compatibility","Revision histories","Product descriptions","Preview samples","Pricing transparency","Versioned downloads","License clarity","Customer onboarding","Refund policy visibility","Content quality reviews","Searchable catalogs","Cross-platform files","Product accessibility","Support knowledge base","Subscription concepts","Delivery verification","Product roadmap"]},{"slug":"blockchain","title":"Blockchain & Digital Trust","focus":"Distributed systems fundamentals and practical risk disclosure","url":"/blockchain/","topics":["Ledger fundamentals","Wallet safety","Transaction lifecycle","Private-key protection","Smart contract review","Gas fee estimation","Chain compatibility","Token design limitations","Distributed consensus","Audit trails","Payment verification","Address validation","Scam recognition","Network congestion","Custody choices","Compliance awareness","On-chain analytics","Data privacy tradeoffs","Irreversibility warnings","Security education"]},{"slug":"market","title":"E-commerce & Marketplaces","focus":"Trustworthy online catalog design, order management and seller workflows","url":"/ventures/ecommerce/","topics":["Product taxonomy","Merchant onboarding","Inventory accuracy","Search filters","Checkout usability","Order status design","Payment reconciliation","Fraud prevention","Supplier directories","Return processes","Shipping disclosures","Digital fulfillment","Price transparency","Marketplace moderation","Customer communication","Vendor reporting","Data minimization","Review integrity","Conversion research","Operations dashboards"]},{"slug":"studio","title":"Creative Studio & Media","focus":"Production methods, consistent media and responsible visual storytelling","url":"/studio/","topics":["Creative briefs","Visual direction","Scene composition","Color systems","Brand consistency","Typography choices","Motion pacing","Accessible animation","Sound design plans","Storyboard methods","Video editing workflows","Digital illustration","Image licensing","Asset metadata","Responsive artwork","Creative QA","Portfolio curation","Presentation templates","Content distribution","Studio operations"]},{"slug":"economy","title":"Economics & Management","focus":"Decision frameworks, measurement and practical business modeling","url":"/economy/","topics":["Cost structures","Margin analysis","Cash planning","Scenario forecasts","Market segmentation","Demand estimation","Pricing strategy","Break-even modeling","Business KPIs","Procurement controls","Production scheduling","Inventory risk","Resource allocation","Customer lifetime value","Working capital","Project budgeting","Financial controls","Strategy options","Performance review","Decision documentation"]},{"slug":"agriculture","title":"Agriculture & Rural Systems","focus":"Farm economics, applied agronomy and production planning","url":"/ventures/agriculture/","topics":["Crop enterprise budgets","Farm machinery planning","Horticulture operations","Greenhouse energy use","Livestock management","Poultry unit economics","Aquaculture production","Soil testing basics","Water allocation","Seed selection","Plant genetics concepts","Integrated pest management","Fertilizer planning","Precision agriculture","Harvest logistics","Farm labor planning","Risk and insurance","Rural value chains","Biosecurity checklists","Sustainable resource use"]},{"slug":"jewelry","title":"Gold, Jewelry & Gemstones","focus":"Craft documentation, traceability and careful commodity education","url":"/ventures/jewelry-gold/","topics":["Gold purity concepts","Weight reconciliation","Manufacturing records","Gemstone grading basics","Authenticity verification","Workshop safety","Assay documentation","Repair workflow","Jewelry CAD planning","Pricing components","Inventory lot tracking","Customer specifications","Ethical sourcing","Quality control steps","Scrap recovery accounting","Hallmark interpretation","Gemstone handling","Secure order records","Display design","After-sales care"]},{"slug":"carpets","title":"Carpets & Textile Heritage","focus":"Handwoven textile knowledge, materials and ethical presentation","url":"/ventures/carpets/","topics":["Weaving techniques","Fiber identification","Natural dyes","Regional motifs","Knot density","Condition reporting","Provenance records","Conservation practices","Authenticity indicators","Photography planning","Catalog terminology","Dimensions and grading","Age assessment limits","Storage conditions","Cleaning precautions","Retail storytelling","Value appraisal factors","Artisan attribution","Buyer education","Cultural heritage"]},{"slug":"hospitality","title":"Hospitality, Cafés & Food","focus":"Guest-centered service planning and practical hospitality management","url":"/ventures/hospitality/","topics":["Guest journey mapping","Room service workflows","Booking clarity","Food safety basics","Menu engineering","Recipe costing","Allergen disclosure","Cafe service design","Restaurant layout","Staff training","Supplier hygiene","Feedback management","Waste reduction","Local sourcing","Guest accessibility","Shift scheduling","Brand storytelling","Service recovery","Quality measurement","Seasonal planning"]},{"slug":"partners","title":"Company & Global Collaboration","focus":"Transparent project cooperation, technical delivery and client trust","url":"/company/","topics":["Capability statements","Project discovery","Needs assessment","Proposal scoping","Milestone planning","Stakeholder mapping","NDA considerations","Portfolio evidence","Canada-facing UX","Cross-border coordination","IP ownership basics","Contract deliverables","Quality acceptance","Maintenance agreements","Security commitments","Communication cadence","Pilot project design","Outcome measurement","Long-term partnerships","Transparent reporting"]}]''')
PATTERN=re.compile(r'<section class="mpo-ring" data-orbit="[^"]+"[^>]*>.*?</section>',re.S)
CARD=re.compile(r'<li class="mpo-orbit-item">.*?</li>',re.S)
END_ORBITS=re.compile(r'</section>\s*</div>\s*<div class="mpo-orbit-bottom">')
DESC=[
 "Frame a clear objective and define measurable acceptance criteria.",
 "Compare practical options, complexity and documented trade-offs.",
 "Outline steps, dependencies and the evidence needed for decisions.",
 "Evaluate the user experience, accessibility and intended outcomes.",
 "Translate requirements into a bounded and reviewable implementation plan.",
 "Identify security, compliance and operational risks before release.",
 "Collect reliable inputs and distinguish examples from observed facts.",
 "Plan tests, review points and quality controls for each deliverable.",
 "Make underlying assumptions transparent and review alternative scenarios.",
 "Document processes so a specialist can audit the results.",
 "Check usability on mobile and low-bandwidth connections.",
 "Estimate resources and set realistic milestones for implementation.",
 "Clarify data ownership, privacy constraints and retention requirements.",
 "Verify claims, provenance and documentation before publication.",
 "Consider maintenance, support and version control requirements.",
 "Define measurable service levels and meaningful evaluation metrics.",
 "Assess scalability without promising unverified production capability.",
 "Review stakeholder needs, approvals and handover responsibilities.",
 "Surface limitations, failure modes and corrective actions early.",
 "Summarize the next step and a practical checklist for evaluation."
]
CSS="""<style id="mpw-17x20-mainonly-style">
/* Main homepage only: 17 real tracks, 20 distinct entries in each. */
.mojplaywin-home .mpo-orbits{display:grid;gap:clamp(22px,3vw,40px)}
.mojplaywin-home .mpo-orbits>.mpo-ring{min-width:0;content-visibility:auto;contain-intrinsic-size:auto 420px;scroll-margin-top:70px}
.mojplaywin-home .mpo-orbits>.mpo-ring .mpo-ring-head{margin-bottom:12px}
.mojplaywin-home .mpo-topic-visual{position:relative;overflow:hidden;display:grid;place-items:center;
 width:100%;aspect-ratio:1.28;background:
 radial-gradient(circle at 23% 19%,hsla(var(--mpo-hue),72%,68%,.37),transparent 42%),
 radial-gradient(circle at 78% 71%,hsla(calc(var(--mpo-hue) + 48),72%,50%,.25),transparent 39%),
 linear-gradient(145deg,#131a22,#070b11 70%);
 border-bottom:1px solid rgba(233,181,88,.32)}
.mojplaywin-home .mpo-topic-visual:before{content:"";width:54%;aspect-ratio:1;
 border:2px solid hsla(var(--mpo-hue),76%,74%,.64);border-radius:28%;transform:rotate(32deg);
 box-shadow:inset 0 0 24px hsla(var(--mpo-hue),74%,45%,.19),0 0 22px hsla(var(--mpo-hue),74%,50%,.18)}
.mojplaywin-home .mpo-topic-glyph{position:absolute;z-index:1;font-size:clamp(1.5rem,2vw,2.4rem);
 font-weight:750;letter-spacing:.04em;color:#ffe7af;text-shadow:0 3px 9px #000a}
.mojplaywin-home .mpo-topic-card .mpo-orbit-card-copy{min-height:112px}
.mojplaywin-home .mpo-topic-card .mpo-orbit-card-copy strong{font-size:.88rem}
.mojplaywin-home .mpo-topic-card .mpo-orbit-card-copy small{font-size:.66rem;line-height:1.45}
@media(max-width:600px){.mojplaywin-home .mpo-orbits{gap:24px}
 .mojplaywin-home .mpo-orbits>.mpo-ring{contain-intrinsic-size:auto 410px}
 .mojplaywin-home .mpo-topic-card .mpo-orbit-card-copy{min-height:110px}}
@media(prefers-reduced-motion:reduce){
 .mojplaywin-home .mpo-topic-card,.mojplaywin-home .mpo-topic-visual{animation:none!important;transition:none!important}}
</style>"""
AUTOSTART="""<script id="mpw-17x20-mainonly-autostart">
/* Start existing gentle orbit control after its defer scripts initialize.
   Users retain the original pause toggle and arrow/manual scrolling. */
window.addEventListener('load',function(){
  if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  var control=document.querySelector('.mojplaywin-home [data-orbit-toggle]');
  if(control&&control.getAttribute('aria-pressed')==='false'){control.click();}
},{once:true});
</script>"""
def sha(data):return hashlib.sha256(data).hexdigest()
def safe():
    if not ROOT.is_dir() or ROOT.is_symlink() or PAGE.parent.is_symlink():
        raise RuntimeError("unsafe main-owned root")
    if HT.is_symlink() or not HT.is_file() or sha(HT.read_bytes())!=HT_SHA:
        raise RuntimeError("server routing fingerprint changed")
    if PAGE.is_symlink() or not PAGE.is_file() or PAGE.stat().st_size>1000000:
        raise RuntimeError("main homepage file missing or unsafe")
    if BACKROOT.is_symlink():raise RuntimeError("private backup root symlink")
def render_card(row_no,card_no,row):
    topic=row["topics"][card_no]
    hue=((row_no*20+card_no)*83)%360  # 340 visually distinct CSS visual tints
    glyph="".join(s[0] for s in topic.split()[:2]).upper()
    title=html.escape(topic,quote=True)
    desc=html.escape(row["focus"]+". "+DESC[card_no],quote=True)
    href=html.escape(row["url"],quote=True)
    return (f'<li class="mpo-orbit-item"><a class="mpo-orbit-card mpo-topic-card" href="{href}">'
       f'<span class="mpo-topic-visual" aria-hidden="true" style="--mpo-hue:{hue}">'
       f'<span class="mpo-topic-glyph">{html.escape(glyph)}</span></span>'
       f'<span class="mpo-orbit-card-copy"><strong>{title}</strong><small>{desc}</small></span></a></li>')
def render_row(index,row):
    slug=html.escape(row["slug"],quote=True)
    title=html.escape(row["title"],quote=True)
    focus=html.escape(row["focus"],quote=True)
    label=f"{index+1:02d} / {row['title'].upper()}"
    cards="\n".join(render_card(index,j,row) for j in range(20))
    return (f'<section class="mpo-ring" data-orbit="{slug}" aria-labelledby="mpo-ring-{slug}">\n'
      f'<div class="mpo-ring-head"><div><span class="mpo-eyebrow">{html.escape(label)}</span>'
      f'<h2 id="mpo-ring-{slug}">{title}</h2><p>{focus}</p></div>'
      f'<div class="mpo-ring-controls">'
      f'<button type="button" class="mpo-ring-arrow" data-orbit-prev aria-label="Previous {title} cards"><span aria-hidden="true">‹</span></button>'
      f'<button type="button" class="mpo-ring-arrow" data-orbit-next aria-label="Next {title} cards"><span aria-hidden="true">›</span></button>'
      f'</div></div>\n<div class="mpo-track-shell"><div class="mpo-ring-ellipse" aria-hidden="true"></div>'
      f'<ul class="mpo-orbit-track" tabindex="0" aria-label="{html.escape(label)} scrollable cards">'
      f'{cards}</ul></div></section>')
def rewrite(raw):
    if sha(raw)!=EXPECTED_SHA:raise RuntimeError("main source SHA drift")
    doc=raw.decode("utf-8")
    if MARKER in doc or 'id="mpw-17x20-mainonly-autostart"' in doc:
        raise RuntimeError("already installed")
    tracks=list(PATTERN.finditer(doc))
    if len(tracks)!=3 or doc.count('class="mpo-orbit-card"')!=18:
        raise RuntimeError("original 3 rows with 6 cards are not intact")
    if [x.group().count('class="mpo-orbit-card"') for x in tracks]!=[6,6,6]:
        raise RuntimeError("original 6 cards per row changed")
    if len(ROWS)!=17 or any(len(x["topics"])!=20 for x in ROWS):
        raise RuntimeError("topic dataset not 17x20")
    if [x.group(0).split('data-orbit="')[1].split('"')[0] for x in tracks]!=['web','digital','ventures']:
        raise RuntimeError("original row identifiers changed")
    fragments=[]
    for row_no,match in enumerate(tracks):
        original=match.group()
        newcards="\n".join(render_card(row_no,j,ROWS[row_no]) for j in range(6,20))
        if original.count("</ul>")!=1:raise RuntimeError("row list unexpected")
        fragments.append(original.replace("</ul>",newcards+"\n</ul>",1))
    # First three original sections are replaced ONLY to append 14 new cards.
    head=doc[:tracks[0].start()]
    between=[doc[tracks[i].end():tracks[i+1].start()] for i in (0,1)]
    tail=doc[tracks[-1].end():]
    extra="\n"+"\n".join(render_row(i,ROWS[i]) for i in range(3,17))+"\n"
    end_marker=re.search(r'^\s*</div>\s*<div class="mpo-orbit-bottom">',tail,re.S)
    if not end_marker:raise RuntimeError("orbit wrapper end changed")
    rebuilt=head+fragments[0]+between[0]+fragments[1]+between[1]+fragments[2]+extra+tail
    rebuilt=rebuilt.replace('aria-label="Three interactive project and service orbits"',
                            'aria-label="Seventeen interactive project and service rows"',1)
    if rebuilt.count("</head>")!=1 or rebuilt.count("</body>")!=1:raise RuntimeError("page structure changed")
    rebuilt=rebuilt.replace("</head>",CSS+"\n</head>",1)
    rebuilt=rebuilt.replace("</body>",AUTOSTART+"\n</body>",1)
    sections=list(PATTERN.finditer(rebuilt))
    if len(sections)!=17 or any(x.group().count('class="mpo-orbit-card"')+
       x.group().count('class="mpo-orbit-card mpo-topic-card"')!=20 for x in sections):
        raise RuntimeError("17 by 20 structural count failed")
    if rebuilt.count('class="mpo-orbit-card"')!=18:
        raise RuntimeError("original 18 photo cards modified")
    if rebuilt.count('class="mpo-orbit-card mpo-topic-card"')!=322:
        raise RuntimeError("322 added topic cards missing")
    for old in tracks:
        for item in CARD.findall(old.group()):
            if item not in rebuilt:raise RuntimeError("one original card was changed")
    if rebuilt.count('data-mpw-copyright-founder="true"')!=1:
        raise RuntimeError("previous final copyright founder disturbed")
    return rebuilt.encode("utf-8")
def atomic(target,blob,run):
    tmp=target.parent/(".mpw-17x20-"+run+".tmp")
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,target)
    finally:
        if tmp.exists():tmp.unlink()
def folder(run):
    if not re.fullmatch(r"[0-9]{8,14}",run):raise RuntimeError("bad run number")
    return BACKROOT/("run-"+run)
def statewrite(base,obj,run):
    temp=base/("state-"+run+".tmp")
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(obj,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    os.replace(temp,base/"state.json")
def rollback(run):
    base=folder(run)
    obj=json.loads((base/"state.json").read_text())
    if obj["run"]!=run:raise RuntimeError("backup run mismatch")
    old=(base/"original.html").read_bytes()
    if sha(old)!=EXPECTED_SHA:raise RuntimeError("original backup SHA invalid")
    current=PAGE.read_bytes()
    if sha(current)==obj["new"]:
        atomic(PAGE,old,run)
    elif sha(current)!=EXPECTED_SHA:
        raise RuntimeError("concurrent site edit; abort rollback")
    obj["phase"]="rolled_back";statewrite(base,obj,run)
    print(json.dumps({"classification":"MPW_17x20_MAIN_ONLY_ROLLBACK_VERIFIED",
         "current_sha":sha(PAGE.read_bytes()),"subsites_unchanged":True,"passenger_restart":False},sort_keys=True))
def install(run):
    safe()
    old=PAGE.read_bytes()
    new=rewrite(old)
    base=folder(run)
    if base.exists():raise RuntimeError("release already exists")
    BACKROOT.mkdir(mode=0o700,exist_ok=True);os.chmod(BACKROOT,0o700)
    base.mkdir(mode=0o700)
    p=base/"original.html"
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:f.write(old);f.flush();os.fsync(f.fileno())
    if sha(p.read_bytes())!=EXPECTED_SHA:raise RuntimeError("backup hash mismatch")
    obj={"run":run,"phase":"armed","old":EXPECTED_SHA,"new":sha(new)}
    statewrite(base,obj,run)
    watchdog='''import hashlib,json,os,sys,time
from pathlib import Path
time.sleep(320)
base=Path(sys.argv[1]);target=Path(sys.argv[2])
try:
 info=json.loads((base/"state.json").read_text())
 if info["phase"]!="armed":raise SystemExit
 old=(base/"original.html").read_bytes()
 if hashlib.sha256(old).hexdigest()!=info["old"]:raise SystemExit
 if hashlib.sha256(target.read_bytes()).hexdigest()!=info["new"]:raise SystemExit
 tmp=target.with_name(".mpw-17x20-watchdog-"+info["run"]+".tmp")
 fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,"wb") as f:f.write(old);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o644);os.replace(tmp,target)
 info["phase"]="watchdog_rolled_back"
 (base/"state.json").write_text(json.dumps(info,sort_keys=True))
except Exception:pass
'''
    wp=base/"watchdog.py";wp.write_text(watchdog);os.chmod(wp,0o600)
    proc=subprocess.Popen([sys.executable,str(wp),str(base),str(PAGE)],
      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    os.kill(proc.pid,0)
    atomic(PAGE,new,run)
    if sha(PAGE.read_bytes())!=obj["new"]:
        rollback(run);raise RuntimeError("installed bytes mismatch")
    print(json.dumps({"classification":"MPW_MAIN_ONLY_17x20_INSTALLED_PENDING_HTTP",
       "rows":17,"cards_per_row":20,"cards_total":340,"original_cards_preserved":18,
       "new_photo_repeats":0,"subsites_modified":False,"passenger_restart":False},sort_keys=True))
def commit(run):
    safe()
    base=folder(run);obj=json.loads((base/"state.json").read_text())
    if obj["run"]!=run or obj["phase"]!="armed":raise RuntimeError("unarmed release")
    if sha(PAGE.read_bytes())!=obj["new"]:raise RuntimeError("release SHA drift")
    obj["phase"]="committed";statewrite(base,obj,run)
    print(json.dumps({"classification":"MPW_17x20_LIVE_COMMITTED","rows":17,"cards":340,
       "payment_data_unchanged":True,"passenger_restart":False},sort_keys=True))
if __name__=="__main__":
    try:
        if len(sys.argv)!=3:raise RuntimeError("expected mode/run")
        mode,run=sys.argv[1:]
        if mode=="install":install(run)
        elif mode=="rollback":rollback(run)
        elif mode=="commit":commit(run)
        else:raise RuntimeError("unsupported mode")
    except Exception as e:
        print(json.dumps({"classification":"MPW_17x20_RELEASE_REFUSED",
           "error_type":type(e).__name__,"live_site_approved":False},sort_keys=True))
        raise SystemExit(1)

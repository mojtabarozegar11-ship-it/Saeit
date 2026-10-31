"""Ten English course posters on independent personal website with a verified owner photograph.

All artwork is deterministic SVG and embeds only the hash-pinned owner-selected
portrait already approved for the personal website. Do not claim that enrollment,
payment, credentials, or financial outcomes have been confirmed.
"""
from __future__ import annotations
from html import escape
import math
import base64
import hashlib
from pathlib import Path

from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET

SITE="/mojtaba.roozegar/"
BASE=SITE+"social-command/"
POSTER_BASE=BASE+"posters/"
GALLERY=BASE+"courses/"

COURSES=(
    {
        "slug":"business",
        "title":"Business Development Course",
        "lines":("BUILD A BUSINESS","THAT CAN GROW"),
        "summary":"A practical introduction to launching, managing and growing a business.",
        "subtitle":"Business strategy | Sales | Operations",
        "features":("Build a clear business model","Plan cash flow and sustainable sales","Measure marketing and performance"),
        "palette":("#07182c","#173c65","#f6c76a","#f8e5bc","#8fc1ff"),
        "index":"01",
        "alt":"English business course poster with rising charts, city skyline and navy-gold palette.",
    },
    {
        "slug":"agriculture",
        "title":"Increasing Agricultural Income",
        "lines":("GROW FARM INCOME","WITH SMARTER DECISIONS"),
        "summary":"Learn practical ways to improve farm profitability through evidence-based management.",
        "subtitle":"Efficiency | Farm economics | Marketing",
        "features":("Evaluate costs and farm productivity","Explore value-added crop marketing","Manage water, inputs and resources"),
        "palette":("#072b24","#145941","#d6bf6b","#f3efc8","#8de8ba"),
        "index":"02",
        "alt":"English agricultural income poster with crops, farmland and a green-gold palette.",
    },
    {
        "slug":"online-income",
        "title":"How to Earn Money Online",
        "lines":("BUILD DIGITAL SKILLS","EARN ONLINE"),
        "summary":"Explore legitimate digital services, products and online business models.",
        "subtitle":"Digital products | Freelancing | E-commerce",
        "features":("Develop marketable digital skills","Explore freelancing and e-commerce","Plan marketing, costs and risk"),
        "palette":("#071f3f","#145586","#f4c874","#e0f7ff","#6ceadf"),
        "index":"03",
        "alt":"English online income poster with laptop, global connections and an upward digital chart.",
    },
    {
        "slug":"chatgpt",
        "title":"Advanced ChatGPT Training",
        "lines":("MASTER CHATGPT","FOR REAL WORK"),
        "summary":"Use ChatGPT effectively in research, content, operations and business tasks.",
        "subtitle":"Prompting | Research | Automation",
        "features":("Write better prompts and workflows","Apply AI to research and content","Verify outputs and protect sensitive data"),
        "palette":("#1c113f","#46308e","#f4c5ff","#f1e7ff","#77f4dc"),
        "index":"04",
        "alt":"English advanced ChatGPT poster with abstract neural-network illustration in violet.",
    },
    {
        "slug":"research-methods",
        "title":"Scientific Research & Data Analysis",
        "lines":("DESIGN BETTER RESEARCH","TURN DATA INTO INSIGHT"),
        "summary":"Research design, data quality, transparent analysis and evidence-based conclusions.",
        "subtitle":"Methods | Statistics | Evidence",
        "features":("Build reproducible study plans","Organize and interpret reliable data","Communicate limitations and findings"),
        "palette":("#0f2431","#276075","#f4c68d","#eaf8fa","#8fe1e1"),
        "index":"05",
        "alt":"Research and data analysis course poster with an authentic portrait of Mojtaba Roozegar and analytical graphics.",
    },
    {
        "slug":"feasibility",
        "title":"Agribusiness Feasibility & Investment",
        "lines":("ASSESS THE OPPORTUNITY","BEFORE YOU INVEST"),
        "summary":"A practical framework for agricultural project feasibility, scenarios and investment risk.",
        "subtitle":"Feasibility | Risk | Cash flow",
        "features":("Model capital and operating costs","Assess profitability and uncertainty","Build decision-ready feasibility briefs"),
        "palette":("#18292d","#3d625a","#eed08b","#eef4dc","#8ed8b4"),
        "index":"06",
        "alt":"Agribusiness feasibility course poster with an authentic portrait and investment analysis graphics.",
    },
    {
        "slug":"digital-marketing",
        "title":"Digital Marketing & SEO Strategy",
        "lines":("REACH THE RIGHT PEOPLE","MEASURE REAL GROWTH"),
        "summary":"Build discoverable websites, useful content and customer-acquisition strategies.",
        "subtitle":"SEO | Content | Analytics",
        "features":("Map audience needs to search intent","Plan ethical digital campaigns","Measure leads and conversions"),
        "palette":("#10223f","#3458a3","#ffcd82","#f4efff","#a3bbff"),
        "index":"07",
        "alt":"Digital marketing and SEO course poster with an authentic portrait and audience network graphics.",
    },
    {
        "slug":"business-finance",
        "title":"Business Finance & Profit Management",
        "lines":("KNOW YOUR NUMBERS","PROTECT PROFIT"),
        "summary":"Read cash flow, cost structures and profitability for sound management decisions.",
        "subtitle":"Costs | Pricing | Cash flow",
        "features":("Calculate break-even and margins","Build cash-flow forecasts","Use practical financial dashboards"),
        "palette":("#251c29","#6b3a62","#f6cd79","#fff0d9","#e9a6d7"),
        "index":"08",
        "alt":"Business finance course poster with an authentic portrait and profit dashboard illustration.",
    },
    {
        "slug":"food-quality",
        "title":"Food Processing & Quality Systems",
        "lines":("CREATE MORE VALUE","CONTROL EVERY STEP"),
        "summary":"An introduction to value-added food production, process controls and traceability.",
        "subtitle":"Processing | Quality | Traceability",
        "features":("Map production and quality checkpoints","Introduce batch traceability","Evaluate yield and waste reduction"),
        "palette":("#213224","#496d3c","#f1d08c","#f6f3dc","#b2df9d"),
        "index":"09",
        "alt":"Food processing and quality systems course poster with an authentic portrait and process-flow artwork.",
    },
    {
        "slug":"ai-automation",
        "title":"AI Automation for Enterprise Teams",
        "lines":("DESIGN SMART WORKFLOWS","KEEP HUMANS IN CONTROL"),
        "summary":"Apply practical AI assistants and safe workflow automation to everyday operations.",
        "subtitle":"AI workflows | Controls | Productivity",
        "features":("Map repeatable business processes","Design guarded AI-assisted tasks","Measure quality and human oversight"),
        "palette":("#1b193d","#5445a3","#b9ddff","#f2eaff","#98f5e8"),
        "index":"10",
        "alt":"Enterprise AI automation course poster with an authentic portrait and connected workflow artwork.",
    },
)
BY_SLUG={c["slug"]:c for c in COURSES}
ID="mpw-four-course-posters-20261028"


OWNER_PORTRAIT=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17/static/personal_site/official_profile_20261016/portrait.webp")
OWNER_PORTRAIT_SHA256="482cad022c1739a464d17f0e023c69fcd6971d72bc67881f8ec24218bd2d8e41"

def read_owner_photo():
    """Use only the owner-selected portrait. A changed/missing asset fails closed."""
    if OWNER_PORTRAIT.is_symlink() or not OWNER_PORTRAIT.is_file():
        raise RuntimeError("Approved owner photograph is not installed")
    blob=OWNER_PORTRAIT.read_bytes()
    if (not 8000 < len(blob) < 300000 or blob[:4]!=b"RIFF" or
        blob[8:12]!=b"WEBP" or
        hashlib.sha256(blob).hexdigest()!=OWNER_PORTRAIT_SHA256):
        raise RuntimeError("Approved owner portrait checksum or format mismatch")
    return blob

def portrait_layer(owner_webp):
    """Portable self-contained poster: no remote image fetch or face synthesis."""
    if not isinstance(owner_webp,bytes) or not owner_webp:
        raise ValueError("Verified portrait data required")
    encoded=base64.b64encode(owner_webp).decode("ascii")
    return (
      '<defs><clipPath id="ownerPhoto"><rect x="548" y="508" width="286" height="422" rx="28"/></clipPath></defs>'
      '<rect x="537" y="497" width="308" height="444" rx="36" fill="#040a12" opacity=".88"/>'
      '<image x="548" y="508" width="286" height="422" preserveAspectRatio="xMidYMid slice" '
      'clip-path="url(#ownerPhoto)" href="data:image/webp;base64,'+encoded+'"/>'
      '<rect x="548" y="508" width="286" height="422" rx="28" fill="none" stroke="#f4d79b" stroke-width="6"/>'
      '<rect x="542" y="914" width="298" height="49" rx="16" fill="#101c25" opacity=".96"/>'
      '<text x="691" y="945" font-family="Arial,Helvetica,sans-serif" font-size="19" '
      'font-weight="700" text-anchor="middle" fill="#fff1cb">MOJTABA ROOZEGAR</text>'
    )

def _art(slug, hi, ice):
    if slug=="business":
        columns="".join(
            '<rect x="%d" y="%d" width="72" height="%d" rx="9" fill="%s" opacity=".9"/>'%
            (x,975-h,h,hi if i%2 else ice)
            for i,(x,h) in enumerate(zip((150,255,360,465,570,675),(110,185,255,350,420,530)))
        )
        skyline="".join('<rect x="%d" y="%d" width="%d" height="%d" fill="#93b8e0" opacity=".10"/>'%
                        (x,920-h,65,h) for x,h in ((65,175),(195,230),(345,160),(540,240),(775,180)))
        return skyline+columns+(
          '<path d="M130 820 L252 764 L354 730 L455 651 L557 585 L661 492 L751 433" '
          'stroke="%s" stroke-width="19" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'%hi+
          '<path d="M695 431 L770 418 L752 491" stroke="%s" stroke-width="19" fill="none" stroke-linecap="round"/>'%hi+
          '<circle cx="690" cy="520" r="120" fill="%s" opacity=".07"/>'%hi
        )
    if slug=="agriculture":
        fields="".join(
            '<path d="M450 690 Q%d 852 %d 1015" stroke="%s" stroke-width="%d" fill="none" opacity=".6"/>'%
            (x,x+round((x-450)*1.18),ice if i%2 else hi,3+(i%3)*2)
            for i,x in enumerate(range(-250,1200,115))
        )
        leaves=[]
        for x,y,s in ((280,775,1),(452,704,1.5),(626,780,1),(370,850,.7),(546,860,.7)):
            leaves.append('<g transform="translate(%s %s) scale(%s)"><path d="M0 135 V0" stroke="%s" stroke-width="12" stroke-linecap="round"/>'%(x,y,s,hi))
            leaves.append('<path d="M0 73 C-79 70 -88 7 -17 12 C0 22 0 73 0 73Z" fill="%s"/>'%ice)
            leaves.append('<path d="M0 95 C72 87 79 31 20 38 C0 52 0 95 0 95Z" fill="%s"/>'%hi)
            leaves.append('</g>')
        return (
          '<circle cx="450" cy="592" r="135" fill="%s" opacity=".16"/>'%hi+
          '<circle cx="450" cy="592" r="102" fill="%s" opacity=".82"/>'%hi+
          '<path d="M0 930 Q450 640 900 930V1020H0Z" fill="#1b754d" opacity=".67"/>'+
          '<path d="M0 995 Q450 777 900 995V1020H0Z" fill="#0c302b"/>'+
          fields+''.join(leaves)
        )
    if slug=="online-income":
        nodes=''.join('<circle cx="%d" cy="%d" r="17" fill="%s" stroke="#fff" stroke-opacity=".42" stroke-width="3"/>'%
                      (x,y,ice) for x,y in ((180,603),(730,625),(203,837),(729,875)))
        lines=''.join('<path d="M%s %s L%s %s" stroke="%s" stroke-width="6" opacity=".52"/>'%
                      (x,y,u,v,ice) for x,y,u,v in ((180,603,310,692),(730,625,590,692),
                                                   (203,837,315,804),(729,875,588,804)))
        return (lines+nodes+
          '<rect x="245" y="550" width="408" height="295" rx="28" fill="#0a2440" stroke="%s" stroke-width="11"/>'%ice+
          '<rect x="270" y="577" width="356" height="234" rx="12" fill="#1a629c"/>'+
          '<path d="M260 850 H643 L687 893 H214 Z" fill="%s" opacity=".92"/>'%ice+
          '<path d="M332 688 L412 737 L527 615" stroke="%s" stroke-width="20" fill="none" stroke-linecap="round"/>'%hi+
          '<path d="M470 614 L540 604 L535 666" stroke="%s" stroke-width="17" fill="none" stroke-linecap="round"/>'%hi+
          '<rect x="362" y="925" width="176" height="56" rx="28" fill="%s" opacity=".54"/>'%hi
        )

    if slug in ("research-methods","feasibility","digital-marketing","business-finance","food-quality","ai-automation"):
        # A distinctive SVG visual for each new subject, behind the real portrait.
        i=("research-methods","feasibility","digital-marketing","business-finance","food-quality","ai-automation").index(slug)
        bars="".join('<rect x="%d" y="%d" width="56" height="%d" rx="8" fill="%s" opacity=".84"/>'%
                     (115+n*67,890-h,h,hi if (n+i)%2 else ice)
                     for n,h in enumerate((90+i*19,170-i*7,126+i*13,270-i*16,205+i*8)))
        connections="".join('<path d="M%d %d L%d %d" stroke="%s" stroke-width="5" opacity=".6"/>'%
                            (140+n*69,645+(n%2)*75,205+n*69,710+((n+1)%2)*75,ice)
                            for n in range(4))
        glyphs=(
          '<circle cx="285" cy="680" r="124" fill="none" stroke="%s" stroke-width="12"/>'%hi+
          '<path d="M225 704 L270 657 L316 694 L366 615" fill="none" stroke="%s" stroke-width="14"/>'%ice,
          '<path d="M100 900 L180 760 L272 812 L368 630 L460 700" fill="none" stroke="%s" stroke-width="16"/>'%hi,
          '<circle cx="280" cy="700" r="150" fill="none" stroke="%s" stroke-width="8" stroke-dasharray="22 16"/>'%hi+
          '<circle cx="280" cy="700" r="76" fill="none" stroke="%s" stroke-width="11"/>'%ice,
          '<path d="M110 870 C210 835 245 760 335 724 S435 590 500 560" fill="none" stroke="%s" stroke-width="18"/>'%hi,
          '<rect x="160" y="625" width="255" height="255" rx="24" fill="none" stroke="%s" stroke-width="13"/>'%ice+
          '<path d="M215 755 L275 816 L378 680" fill="none" stroke="%s" stroke-width="20"/>'%hi,
          '<circle cx="290" cy="720" r="100" fill="none" stroke="%s" stroke-width="14"/>'%hi+
          '<path d="M192 720 H395 M290 620 V820" stroke="%s" stroke-width="9"/>'%ice,
        )
        return connections+bars+glyphs[i]
    points=[(450+210*math.cos(i*math.pi/6),715+210*math.sin(i*math.pi/6)) for i in range(12)]
    links=[]
    for i,(x,y) in enumerate(points):
        x2,y2=points[(i+1)%len(points)]
        links.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" stroke-width="5" opacity=".65"/>'%(x,y,x2,y2,ice))
        if i%2==0: links.append('<path d="M%.1f %.1f L450 715" stroke="%s" stroke-width="4" opacity=".7"/>'%(x,y,hi))
    nodes=''.join('<circle cx="%.1f" cy="%.1f" r="%d" fill="%s" stroke="#fff" stroke-opacity=".54" stroke-width="4"/>'%
                  (x,y,17 if i%2 else 27,hi if i%2 else ice) for i,(x,y) in enumerate(points))
    return (''.join(links)+nodes+
       '<circle cx="450" cy="715" r="116" fill="#291a68" stroke="%s" stroke-width="14"/>'%ice+
       '<path d="M386 737 C340 655 431 612 460 662 C497 600 595 660 520 725 '
       'C584 792 480 853 455 790 C414 832 359 798 386 737Z" fill="none" '
       'stroke="%s" stroke-width="19" stroke-linecap="round" stroke-linejoin="round"/>'%hi+
       '<circle cx="450" cy="715" r="255" fill="none" stroke="%s" stroke-width="3" stroke-dasharray="10 19" opacity=".3"/>'%hi
    )

def svg_for(slug, portrait_bytes=None):
    course=BY_SLUG[slug]
    owner_photo=read_owner_photo() if portrait_bytes is None else portrait_bytes
    dark,mid,accent,ivory,secondary=course["palette"]
    l1,l2=course["lines"]
    def text(y,content,size,color,weight="700"):
        return ('<text x="450" y="%d" font-family="Arial,Helvetica,sans-serif" '
                'font-size="%d" font-weight="%s" text-anchor="middle" direction="ltr" '
                'fill="%s">%s</text>'%(y,size,weight,color,escape(content)))
    artwork=_art(slug,accent,secondary)
    stars="".join('<circle cx="%d" cy="%d" r="%d" fill="%s" opacity=".6"/>'%
                  ((53+i*117)%850+25,(105+i*179)%940+55,2+i%3,secondary) for i in range(15))
    svg=(
       '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200" '
       'role="img" aria-labelledby="posterTitle posterDesc">'
       '<title id="posterTitle">'+escape(course["title"])+'</title>'
       '<desc id="posterDesc">'+escape(course["alt"])+'</desc>'
       '<defs><linearGradient id="bg" x1="0" y1="0" x2=".95" y2="1">'
       '<stop stop-color="%s"/><stop offset=".68" stop-color="%s"/>'
       '<stop offset="1" stop-color="%s"/></linearGradient>'%(dark,mid,dark)+
       '<radialGradient id="halo"><stop stop-color="%s" stop-opacity=".38"/>'
       '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'%(secondary,secondary)+
       '<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="%s"/>'
       '<stop offset="1" stop-color="%s"/></linearGradient></defs>'%(ivory,accent)+
       '<rect width="900" height="1200" rx="26" fill="url(#bg)"/>'
       '<circle cx="450" cy="660" r="380" fill="url(#halo)"/>'
       '<path d="M-120 1180 L970 350" stroke="%s" stroke-width="65" opacity=".055"/>'%ivory+
       stars+
       '<rect x="24" y="24" width="852" height="1152" rx="18" fill="none" '
       'stroke="%s" stroke-opacity=".56" stroke-width="3"/>'%accent+
       '<rect x="280" y="62" width="340" height="53" rx="26" '
       'fill="%s" fill-opacity=".12" stroke="%s" stroke-opacity=".65"/>'%(accent,accent)+
       text(98,"MOJTABA ROOZEGAR  •  EDUCATION",22,ivory,"500")+
       '<path d="M180 145 H720" stroke="%s" stroke-opacity=".3" stroke-width="2"/>'%accent+
       text(258,l1,56 if len(l1)>16 else 69,ivory)+text(370,l2,50 if len(l2)>17 else 73,accent)+
       text(441,course["subtitle"],29,ivory,"500")+
       artwork+portrait_layer(owner_photo)+
       '<rect x="54" y="1006" width="792" height="150" rx="23" '
       'fill="#020c17" fill-opacity=".48" stroke="%s" stroke-opacity=".6"/>'%accent+
       text(1062,"EXPLORE THE COURSE",35,ivory)+
       '<path d="M280 1086 H620" stroke="%s" stroke-width="2" stroke-opacity=".6"/>'%accent+
       text(1130,"MOJTABA ROOZEGAR | COURSE PREVIEW",23,secondary,"500")+
       '</svg>'
    )
    if len(svg.encode("utf-8"))>460_000:
        raise ValueError("Poster not safely bounded")
    return svg

def _html(course):
    features="".join("<li>"+escape(item)+"</li>" for item in course["features"])
    slug=course["slug"]
    url=POSTER_BASE+slug+".svg"
    return ('<article class="mpw-course-card" id="'+slug+'">'
            '<a class="mpw-course-image" href="'+url+'?v=en-20261031-photo" target="_blank" rel="noopener noreferrer" '
            'aria-label="View poster: '+escape(course["title"])+'">'
            '<img loading="lazy" decoding="async" width="900" height="1200" src="'+url+'?v=en-20261031-photo" alt="'+
            escape(course["alt"],quote=True)+'"></a>'
            '<div class="mpw-course-copy"><h2>'+escape(course["title"])+'</h2><p>'+
            escape(course["summary"])+'</p><h3>What you will explore</h3><ul>'+features+
            '</ul><p class="mpw-course-status">Course overview | Enrollment and payments are not open</p>'
            '<div class="mpw-course-actions"><a href="'+url+'?v=en-20261031-photo" target="_blank" rel="noopener noreferrer">'
            'View poster</a><a href="'+SITE+'contact/">Ask about this course</a></div></div></article>')

@require_GET
def poster(request,slug):
    course=BY_SLUG.get(slug)
    if not course:
        return HttpResponseNotFound("Poster not found")
    try:
        picture=read_owner_photo()
        output=svg_for(slug,picture)
    except (OSError,RuntimeError,ValueError):
        return HttpResponse("Owner photograph temporarily unavailable",status=503,content_type="text/plain")
    out=HttpResponse(output,content_type="image/svg+xml; charset=utf-8")
    out["X-Content-Type-Options"]="nosniff"
    out["Cache-Control"]="public, max-age=120, must-revalidate"
    out["Content-Security-Policy"]="default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox"
    return out

@require_GET
def gallery(request):
    cards="".join(_html(c) for c in COURSES)
    page='''<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow">
<title>Ten Professional Courses | Mojtaba Roozegar</title>
<meta name="description" content="Explore ten practical learning paths across business, agricultural economics, research, digital marketing, finance, quality management and AI with Mojtaba Roozegar.">
<link rel="canonical" href="https://mojplaywin.com/mojtaba.roozegar/social-command/courses/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0e1516;color:#f1e9d9;font:15px/1.85 system-ui,Arial,Helvetica,sans-serif}
header,main,footer{max-width:1210px;margin:auto;padding:clamp(14px,4vw,38px)}a{color:#e6c57e}
h1{font-size:clamp(29px,5vw,49px);margin:10px 0;color:#f3d295}h2{font-size:clamp(20px,2.5vw,28px);color:#f4d69e}
.mpw-kicker{color:#e8c881;letter-spacing:.16em;font-size:12px}
header{padding-top:40px}header p{font-size:17px;color:#d2c8b6;max-width:790px}
nav a{margin-left:15px}.mpw-course-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}
.mpw-course-card{display:grid;grid-template-columns:46% 54%;min-width:0;background:#1b2322;border:1px solid #81714a;border-radius:18px;overflow:hidden;box-shadow:0 22px 50px #0005}
.mpw-course-image{display:block;min-height:100%;background:#152528}
.mpw-course-image img{display:block;width:100%;height:100%;object-fit:cover;aspect-ratio:3/4}
.mpw-course-copy{padding:clamp(12px,2.5vw,25px);min-width:0}.mpw-course-copy h2{margin:0 0 8px}
.mpw-course-copy p{margin:8px 0}.mpw-course-copy h3{font-size:15px;margin:13px 0 4px;color:#dfc7a0}
.mpw-course-copy ul{margin:0;padding-left:20px}.mpw-course-copy li{margin:4px 0}
.mpw-course-status{font-size:12px;color:#e0d3ad;background:#24332a;padding:7px 10px;border-radius:8px}
.mpw-course-actions{display:flex;gap:8px;flex-wrap:wrap;margin:15px 0 0}
.mpw-course-actions a{border:1px solid #a18a58;padding:8px 11px;border-radius:8px;text-decoration:none}
.mpw-course-actions a:hover,.mpw-course-actions a:focus-visible{background:#383524}
footer{color:#d2c8b6}footer p{max-width:850px}
@media(max-width:1060px){.mpw-course-grid{grid-template-columns:1fr}}
@media(max-width:520px){.mpw-course-card{grid-template-columns:1fr}.mpw-course-image img{max-height:550px;object-fit:contain}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important}}
</style></head><body>
<header><div class="mpw-kicker">MOJTABA ROOZEGAR / EDUCATION</div>
<h1>Ten Courses. Practical Skills.</h1>
<p>Explore ten professional learning paths across business, agribusiness, research, marketing and AI. Every self-contained poster features the owner-approved authentic photograph of Mojtaba Roozegar.</p>
<nav><a href="/mojtaba.roozegar/">Back to personal website</a><a href="/mojtaba.roozegar/contact/">Contact and inquiries</a></nav>
</header><main><section class="mpw-course-grid" aria-label="Ten courses and promotional posters">'''+cards+'''</section></main>
<footer><p>This is an early course preview. Dates, tuition, certificates and enrollment will be announced only when confirmed. No earnings or financial results are guaranteed.</p>
<p>© Mojtaba Roozegar · Official Personal Website</p></footer></body></html>'''
    out=HttpResponse(page,content_type="text/html; charset=utf-8")
    out["X-Content-Type-Options"]="nosniff"
    out["Cache-Control"]="public, max-age=300"
    return out

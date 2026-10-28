"""Four original Persian course posters on independent personal website, no paid checkout.

All artwork is deterministic hand-built SVG. Do not present generated human
portraits as an actual teacher, use any private owner photos, or claim that
course enrollment/payment or financial outcomes are already guaranteed.
"""
from __future__ import annotations
from html import escape
import math

from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET

SITE="/mojtaba.roozegar/"
BASE=SITE+"social-command/"
POSTER_BASE=BASE+"posters/"
GALLERY=BASE+"courses/"

COURSES=(
    {
        "slug":"business",
        "title":"دوره کسب‌وکار",
        "lines":("دوره جامع","کسب‌وکار"),
        "summary":"از ایده تا برنامه‌ریزی، فروش و مدیریت پایدار",
        "subtitle":"راه‌اندازی، مدیریت و توسعه کسب‌وکار",
        "features":("طراحی مدل کسب‌وکار","برنامه‌ریزی مالی و فروش","بازاریابی و سنجش عملکرد"),
        "palette":("#07182c","#173c65","#f6c76a","#f8e5bc","#8fc1ff"),
        "index":"01",
        "alt":"پوستر دوره کسب‌وکار؛ نمودار رشد و ساختمان‌های تجاری در طیف سرمه‌ای و طلایی",
    },
    {
        "slug":"agriculture",
        "title":"دوره افزایش درآمد کشاورزی",
        "lines":("افزایش درآمد","کشاورزی"),
        "summary":"بهره‌وری بیشتر، مدیریت هزینه و بازار محصول",
        "subtitle":"مدیریت علمی مزرعه و ارزش‌آفرینی",
        "features":("تحلیل هزینه و بهره‌وری","بازاررسانی و ارزش افزوده","مدیریت آب و منابع"),
        "palette":("#072b24","#145941","#d6bf6b","#f3efc8","#8de8ba"),
        "index":"02",
        "alt":"پوستر افزایش درآمد کشاورزی با نماد مزرعه، خوشه گندم و خورشید به رنگ سبز و طلایی",
    },
    {
        "slug":"online-income",
        "title":"دوره آموزش کسب درآمد از اینترنت",
        "lines":("کسب درآمد","از اینترنت"),
        "summary":"مهارت‌های دیجیتال، خدمات آنلاین و تجارت اینترنتی",
        "subtitle":"از مهارت واقعی تا مدل درآمدی آنلاین",
        "features":("خدمات و محصولات دیجیتال","بازاریابی و فروش آنلاین","مدیریت ریسک و هزینه"),
        "palette":("#071f3f","#145586","#f4c874","#e0f7ff","#6ceadf"),
        "index":"03",
        "alt":"پوستر درآمد اینترنتی با نماد لپ‌تاپ، فروشگاه دیجیتال و اتصال‌های شبکه در زمینه آبی",
    },
    {
        "slug":"chatgpt",
        "title":"دوره تخصصی آموزش چت‌جی‌پی‌تی",
        "lines":("آموزش تخصصی","چت‌جی‌پی‌تی"),
        "summary":"کاربرد حرفه‌ای ChatGPT در تحقیق و کسب‌وکار",
        "subtitle":"پرامپت‌نویسی، تحلیل و اتوماسیون مسئولانه",
        "features":("اصول پرامپت‌نویسی","تحلیل و تولید محتوای حرفه‌ای","کنترل صحت و امنیت اطلاعات"),
        "palette":("#1c113f","#46308e","#f4c5ff","#f1e7ff","#77f4dc"),
        "index":"04",
        "alt":"پوستر آموزش تخصصی چت‌جی‌پی‌تی با نماد شبکه عصبی انتزاعی و مدارهای هوش مصنوعی بنفش",
    },
)
BY_SLUG={c["slug"]:c for c in COURSES}
ID="mpw-mojtaba-four-course-posters-20261028"

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

def svg_for(slug):
    course=BY_SLUG[slug]
    dark,mid,accent,ivory,secondary=course["palette"]
    l1,l2=course["lines"]
    def text(y,content,size,color,weight="700"):
        return ('<text x="450" y="%d" font-family="Noto Sans Arabic,Tahoma,Arial,sans-serif" '
                'font-size="%d" font-weight="%s" text-anchor="middle" direction="rtl" '
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
       text(258,l1,65,ivory)+text(370,l2,77,accent)+
       text(441,course["subtitle"],29,ivory,"500")+
       artwork+
       '<rect x="54" y="1006" width="792" height="150" rx="23" '
       'fill="#020c17" fill-opacity=".48" stroke="%s" stroke-opacity=".6"/>'%accent+
       text(1062,"آشنایی با سرفصل‌ها و برنامه دوره",29,ivory)+
       '<path d="M280 1086 H620" stroke="%s" stroke-width="2" stroke-opacity=".6"/>'%accent+
       text(1130,"وب شخصی مجتبی روزگار  |  معرفی دوره",23,secondary,"500")+
       '</svg>'
    )
    if len(svg.encode("utf-8"))>40_000:
        raise ValueError("Poster not safely bounded")
    return svg

def _html(course):
    features="".join("<li>"+escape(item)+"</li>" for item in course["features"])
    slug=course["slug"]
    url=POSTER_BASE+slug+".svg"
    return ('<article class="mpw-course-card" id="'+slug+'">'
            '<a class="mpw-course-image" href="'+url+'" target="_blank" rel="noopener noreferrer" '
            'aria-label="مشاهده پوستر '+escape(course["title"])+'">'
            '<img loading="lazy" decoding="async" width="900" height="1200" src="'+url+'" alt="'+
            escape(course["alt"],quote=True)+'"></a>'
            '<div class="mpw-course-copy"><h2>'+escape(course["title"])+'</h2><p>'+
            escape(course["summary"])+'</p><h3>محورهای پیشنهادی آموزش</h3><ul>'+features+
            '</ul><p class="mpw-course-status">معرفی دوره | ثبت‌نام و پرداخت در این صفحه فعال نیست</p>'
            '<div class="mpw-course-actions"><a href="'+url+'" target="_blank" rel="noopener noreferrer">'
            'مشاهده پوستر</a><a href="'+SITE+'contact/">پرسش درباره برنامه دوره</a></div></div></article>')

@require_GET
def poster(request,slug):
    course=BY_SLUG.get(slug)
    if not course:
        return HttpResponseNotFound("Poster not found")
    out=HttpResponse(svg_for(slug),content_type="image/svg+xml; charset=utf-8")
    out["X-Content-Type-Options"]="nosniff"
    out["Cache-Control"]="public, max-age=3600"
    out["Content-Security-Policy"]="default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return out

@require_GET
def gallery(request):
    cards="".join(_html(c) for c in COURSES)
    page='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow">
<title>چهار دوره آموزشی | وب مجتبی روزگار</title>
<meta name="description" content="معرفی چهار دوره در زمینه کسب‌وکار، افزایش درآمد کشاورزی، درآمد اینترنتی و استفاده تخصصی از ChatGPT؛ همراه با پوستر و سرفصل‌های پیشنهادی.">
<link rel="canonical" href="https://mojplaywin.com/mojtaba.roozegar/social-command/courses/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0e1516;color:#f1e9d9;font:15px/1.85 system-ui,"Noto Sans Arabic",Tahoma,sans-serif}
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
.mpw-course-copy ul{margin:0;padding-right:20px}.mpw-course-copy li{margin:4px 0}
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
<h1>چهار مسیر یادگیری و توسعه مهارت</h1>
<p>آشنایی با دوره‌های کسب‌وکار، مدیریت اقتصادی کشاورزی، کسب درآمد از اینترنت و کار حرفه‌ای با چت‌جی‌پی‌تی. پوسترهای این صفحه اصل و بدون تصویر ساختگی مدرس هستند.</p>
<nav><a href="/mojtaba.roozegar/">بازگشت به وب شخصی</a><a href="/mojtaba.roozegar/contact/">تماس و پرسش</a></nav>
</header><main><section class="mpw-course-grid" aria-label="چهار پوستر و معرفی دوره‌ها">'''+cards+'''</section></main>
<footer><p>وضعیت انتشار: معرفی اولیه سرفصل‌ها. مدت، برنامه جلسات، شهریه، مدرک و زمان ثبت‌نام فقط پس از اعلام رسمی تعیین می‌شوند. هیچ تضمین درآمدی ارائه نمی‌شود.</p>
<p>© Mojtaba Roozegar · وب شخصی مجتبی روزگار</p></footer></body></html>'''
    out=HttpResponse(page,content_type="text/html; charset=utf-8")
    out["X-Content-Type-Options"]="nosniff"
    out["Cache-Control"]="public, max-age=300"
    return out

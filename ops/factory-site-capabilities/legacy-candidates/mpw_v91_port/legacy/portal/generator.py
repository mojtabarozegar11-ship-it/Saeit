"""Deterministic, stdlib-only production. No model/API/VPS access or fabricated facts."""
import html
from urllib.parse import urlsplit

class InputError(ValueError):
    pass

def valid_sources(sources):
    if not isinstance(sources, list):
        return []
    result=[]
    for s in sources[:12]:
        if not isinstance(s,str):
            continue
        s=s.strip()
        try:
            parsed=urlsplit(s)
            if parsed.scheme == 'https' and parsed.hostname and len(s) <= 400:
                result.append(s)
        except ValueError:
            continue
    return list(dict.fromkeys(result))

def article_draft(title, facts, sources, language='fa'):
    """Compose an editorial draft only from contributor-provided facts, NEVER auto-publish."""
    if language not in ('fa','en') or not isinstance(facts,list):
        raise InputError('unsupported_language_or_facts')
    values=[str(x).strip() for x in facts if isinstance(x,str) and 30<=len(x.strip())<=1200]
    refs=valid_sources(sources)
    if len(values)<3 or not refs:
        raise InputError('at_least_three_facts_and_one_https_source_required')
    title=title.strip()
    if not title or len(title)>200:
        raise InputError('invalid_title')
    if language=='fa':
        intro=f'این مطلب، پیش‌نویس آموزشی درباره «{title}» است و از داده‌های ارائه‌شده توسط سردبیر تهیه شده است. صحت منابع و نتیجه‌گیری نهایی باید پیش از انتشار بازبینی شود.'
        closing='نتیجه‌گیری: برای تصمیم اجرایی، شرایط محل، زمان، هزینه و مستندات تخصصی مرتبط نیز باید مستقل بررسی شوند.'
    else:
        intro=f'This is an editorial learning draft on “{title}” assembled solely from contributor-provided points. Sources and conclusions require human verification before publication.'
        closing='Conclusion: Decisions also require independent verification of local conditions, timing, costs and relevant technical evidence.'
    body='\n\n'.join([intro]+values+[closing])
    summary=(values[0][:270] + ('…' if len(values[0])>270 else ''))
    return {'title':title,'summary':summary,'body':body,'source_links':refs}

def cost_planner_html(language='fa'):
    if language not in ('fa','en'):
        raise InputError('unsupported_language')
    fa=language=='fa'
    direction='rtl' if fa else 'ltr'
    t={
      'title': 'برنامه‌ریز هزینه و سود تولید' if fa else 'Production Cost & Profit Planner',
      'lead':'ابزار مستقل برآورد اولیه برای مزرعه، گلخانه یا کارگاه؛ بدون ارسال اطلاعات به سرور.' if fa else 'Offline estimate for farms, greenhouses and workshops; no data is transmitted.',
      'fixed':'هزینه ثابت (تومان)' if fa else 'Fixed costs (CAD)',
      'variable':'هزینه متغیر هر واحد' if fa else 'Variable cost per unit',
      'price':'قیمت فروش هر واحد' if fa else 'Selling price per unit',
      'count':'تعداد واحد' if fa else 'Units produced',
      'btn':'محاسبه' if fa else 'Calculate',
      'revenue':'درآمد برآوردی' if fa else 'Estimated revenue',
      'cost':'هزینه کل' if fa else 'Total cost',
      'profit':'سود / زیان' if fa else 'Profit / loss',
      'break_even':'نقطه سر به سر (تعداد)' if fa else 'Break-even units',
      'no_break':'دست‌نیافتنی با این قیمت' if fa else 'Not achievable at this price',
      'note':'محاسبه آموزشی است و مالیات، تورم، ریسک و هزینه‌های پنهان را لحاظ نمی‌کند.' if fa else 'Educational estimate; taxes, inflation, risk and hidden costs are excluded.',
      'invalid':'مقادیر بیش از حد بزرگ یا نامعتبر هستند؛ مقدارها را اصلاح کنید.' if fa else 'Values are invalid or too large; please revise the inputs.',
      'lang':language
    }
    labels={k:html.escape(v,quote=True) for k,v in t.items()}
    # HTML and script are fixed source controlled by this module, not editor-provided code.
    return f"""<!doctype html><html lang="{language}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{labels['title']}</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;padding:32px 18px;background:#14241a;color:#f2e8d3;font-family:system-ui,sans-serif}}main{{max-width:850px;margin:auto}}.panel{{background:#203426;border:1px solid #a88b52;border-radius:25px;padding:25px}}h1{{color:#ead19b;font-size:clamp(1.5rem,4vw,2.3rem)}}p{{line-height:1.8}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}label{{display:block;font-weight:600}}input{{display:block;width:100%;margin-top:7px;padding:13px;background:#102016;color:#fff;border:1px solid #827049;border-radius:12px;font-size:1.08rem}}button{{margin-top:24px;padding:13px 24px;background:#e3c37b;border:0;border-radius:12px;color:#1b2b1a;cursor:pointer;font-weight:800}}.results{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:26px}}.result{{padding:17px;border-radius:14px;background:#2a422f}}.result span{{display:block;font-size:.85rem}}.result strong{{display:block;font-size:1.4rem;margin-top:10px;color:#f0d293}}small{{display:block;margin-top:22px;color:#d6cdb7}}#error:not([hidden]){{margin-top:18px;padding:10px 15px;border:1px solid #dcaa9b;border-radius:10px;color:#ffdfd7;background:#4c2525}}@media(max-width:550px){{.grid,.results{{grid-template-columns:1fr}}body{{padding:12px}}}}</style></head>
<body><main><div class="panel"><h1>{labels['title']}</h1><p>{labels['lead']}</p><form id="calc"><div class="grid">
<label>{labels['fixed']}<input id="fixed" type="number" min="0" value="2000000" required></label>
<label>{labels['variable']}<input id="variable" type="number" min="0" value="50000" required></label>
<label>{labels['price']}<input id="price" type="number" min="0" value="95000" required></label>
<label>{labels['count']}<input id="count" type="number" min="0" step="1" value="100" required></label></div><button type="submit">{labels['btn']}</button></form>
<p id="error" role="alert" aria-live="assertive" hidden></p><div class="results" aria-live="polite"><div class="result"><span>{labels['revenue']}</span><strong id="revenue">—</strong></div><div class="result"><span>{labels['cost']}</span><strong id="cost">—</strong></div><div class="result"><span>{labels['profit']}</span><strong id="profit">—</strong></div><div class="result"><span>{labels['break_even']}</span><strong id="break">—</strong></div></div><small>{labels['note']}</small><footer style="margin-top:24px;padding:14px 0;border-top:1px solid #85714c;font-size:.88rem;line-height:1.9">{ 'محقق و پژوهشگر: مجتبی روزگار · مدیرعامل شرکت کشت و صنعت زمرد ملل' if fa else 'Editorial imprint: Mojtaba Roozegar · Researcher · CEO, Zomorod Melal' }<br><small>{ 'این ابزار محاسباتی با سامانه سایت تولید شده و تأیید فنی آن جداگانه انجام می‌شود.' if fa else 'This tool was assembled by a site system and requires independent technical validation.' }</small></footer></div></main>
<script>(function(){{'use strict';const fmt=new Intl.NumberFormat('{language}');const read=id=>Number(document.getElementById(id).value);const set=(id,value)=>{{document.getElementById(id).textContent=value}};const error=document.getElementById('error');const invalid='{labels['invalid']}';
function calculate(e){{if(e)e.preventDefault();let f=read('fixed'),v=read('variable'),p=read('price'),n=read('count');
let revenue=p*n,cost=f+v*n,profit=revenue-cost,breakeven=p>v?Math.ceil(f/(p-v)):(f===0&&p===v?0:null);
let finite=[f,v,p,n,revenue,cost,profit].every(x=>Number.isFinite(x)&&Number.isSafeInteger(x));
let valid=finite&&[f,v,p,n].every(x=>x>=0)&&n<=1000000&&
  (breakeven===null||(Number.isSafeInteger(breakeven)&&breakeven>=0));
if(!valid){{error.hidden=false;error.textContent=invalid;for(const id of ['revenue','cost','profit','break'])set(id,'—');return;}}
error.hidden=true;error.textContent='';
set('revenue',fmt.format(revenue));set('cost',fmt.format(cost));set('profit',fmt.format(profit));set('break',breakeven===null?'{labels['no_break']}':fmt.format(breakeven));}}document.getElementById('calc').addEventListener('submit',calculate);calculate();}})();</script></body></html>"""

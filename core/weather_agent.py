import json
import os
from datetime import datetime, timezone as utc_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils import timezone

from .met_weather_adapter import SOURCE_MODEL, normalize_locationforecast
from .canonical_content_owner import require_canonical_content_owner

PROVINCES = [
 ('آذربایجان شرقی','تبریز',38.0962,46.2738),('آذربایجان غربی','ارومیه',37.5527,45.0761),('اردبیل','اردبیل',38.2498,48.2933),('اصفهان','اصفهان',32.6546,51.6680),('البرز','کرج',35.8400,50.9391),('ایلام','ایلام',33.6374,46.4227),('بوشهر','بوشهر',28.9234,50.8203),('تهران','تهران',35.6892,51.3890),('چهارمحال و بختیاری','شهرکرد',32.3256,50.8644),('خراسان جنوبی','بیرجند',32.8663,59.2211),('خراسان رضوی','مشهد',36.2605,59.6168),('خراسان شمالی','بجنورد',37.4750,57.3333),('خوزستان','اهواز',31.3183,48.6706),('زنجان','زنجان',36.6736,48.4787),('سمنان','سمنان',35.5729,53.3971),('سیستان و بلوچستان','زاهدان',29.4963,60.8629),('فارس','شیراز',29.5918,52.5837),('قزوین','قزوین',36.2688,50.0041),('قم','قم',34.6416,50.8746),('کردستان','سنندج',35.3219,46.9862),('کرمان','کرمان',30.2839,57.0834),('کرمانشاه','کرمانشاه',34.3142,47.0650),('کهگیلویه و بویراحمد','یاسوج',30.6682,51.5880),('گلستان','گرگان',36.8456,54.4393),('گیلان','رشت',37.2808,49.5832),('لرستان','خرم‌آباد',33.4878,48.3558),('مازندران','ساری',36.5633,53.0601),('مرکزی','اراک',34.0917,49.6892),('هرمزگان','بندرعباس',27.1832,56.2666),('همدان','همدان',34.7980,48.5146),('یزد','یزد',31.8974,54.3569),
]
SOURCE_URL = 'https://api.met.no/weatherapi/locationforecast/2.0/'
SOURCE_LICENSE = 'https://creativecommons.org/licenses/by/4.0/'
SOURCE_ATTRIBUTION = 'Weather forecast from MET Norway (Norwegian Meteorological Institute)'


def _fetch(lat, lon, days=7):
    # MET Norway Terms of Service (revision 2026-11-05) expressly require
    # an authorized HUMAN to read and accept the legally binding terms.
    # AI delegation, public availability and a configured User-Agent do NOT
    # constitute such acceptance. Default fail closed before cache/network IO.
    if os.getenv('MOJ_MET_NORWAY_TOS_ACCEPTED_BY_OWNER') != '1':
        raise RuntimeError('MET_NORWAY_OWNER_TOS_ACCEPTANCE_REQUIRED')
    # Respect the provider's Expires header. Unlike Open-Meteo's free API,
    # MET Norway permits commercial usage under CC BY 4.0 with attribution.
    key = f'met_norway_locationforecast_v1:{lat:.4f}:{lon:.4f}'
    existing = cache.get(key)
    if existing is not None:
        return existing
    params = urlencode({'lat': f'{lat:.4f}', 'lon': f'{lon:.4f}'})
    req = Request(SOURCE_URL + 'compact?' + params, headers={
        'User-Agent': 'ZomorodMelalWeather/1.0 (https://zomorodmelal.ir/contact/)',
        'Accept': 'application/json',
    })
    with urlopen(req, timeout=18) as response:
        payload = json.load(response)
        expiry_header = response.headers.get('Expires')
    if expiry_header:
        try:
            expires = parsedate_to_datetime(expiry_header)
            ttl = max(0, int((expires - datetime.now(utc_timezone.utc)).total_seconds()))
        except (ValueError, TypeError):
            ttl = 0
    else:
        ttl = 0
    # Iran lies outside the Nordic region. MET Norway's Locationforecast
    # service requires at least 3 hours between identical requests there,
    # even if the Expires header is sooner or absent. Respect longer expiry.
    cache.set(key, payload, timeout=max(ttl, 3 * 60 * 60))
    return payload


def _risk_flags(day):
    flags=[]
    if day.get('max_c') is not None and day['max_c'] >= 40: flags.append('گرمای شدید')
    if day.get('min_c') is not None and day['min_c'] <= 0: flags.append('سرمای یخبندان')
    if day.get('rain_mm') is not None and day['rain_mm'] >= 25: flags.append('بارش قابل توجه')
    if day.get('wind_kmh') is not None and day['wind_kmh'] >= 50: flags.append('باد شدید')
    return flags


def province_forecast(days=7):
    output = []
    for name, capital, lat, lon in PROVINCES:
        raw = _fetch(lat, lon, days)
        normalized = normalize_locationforecast(raw, days=days)
        output.append({'province':name,'capital':capital,'latitude':lat,'longitude':lon,**normalized,'data_source_models':[SOURCE_MODEL]})
    return output


def build_public_report(data):
    today = timezone.localdate().isoformat()
    lines = [f'گزارش روزانه هواشناسی ایران — {today}', '', 'برآورد روزانهٔ مراکز استان‌ها از داده‌های زمان‌بندی‌شدهٔ MET Norway تهیه شده است. این داده‌ها خروجی یک ارائه‌دهنده‌اند و اجماع چند مدل نیستند. دما، باد و بارش روزانه از بازه‌های ساعتی و چندساعته برآورد شده‌اند.']
    for item in data:
        p = item['forecast'][0]
        flags='، '.join(_risk_flags(p)) or 'بدون پرچم هشدار خودکار'
        probability = f"{p['rain_probability']}٪" if p['rain_probability'] is not None else 'ناموجود در منبع'
        rain = f"{p['rain_mm']} میلی‌متر" if p['rain_mm'] is not None else 'ناموجود'
        wind = f"{p['wind_kmh']} km/h" if p['wind_kmh'] is not None else 'ناموجود'
        lines.append(f"• {item['province']} ({item['capital']}): {p['min_c']} تا {p['max_c']}°C، احتمال بارش {probability}، بارش برآوردی {rain}، باد تا {wind}؛ {flags}")
    lines += ['', f'داده: {SOURCE_ATTRIBUTION} — {SOURCE_URL}؛ مجوز انتساب CC BY 4.0: {SOURCE_LICENSE}.', 'تقسیم بارش دوره‌های چندساعته میان روزها تقریبی است؛ نبود احتمال بارش در منبع به معنی احتمال صفر نیست. این پیش‌بینی جایگزین هشدارهای رسمی سازمان هواشناسی کشور نیست.']
    return '\n'.join(lines)


def generate_research_contents(weather_summary):
    """No paid generation until a per-task one-time scoped grant exists.

    Daily environment flags and the presence of OPENAI_API_KEY are *not*
    authoritative spending approvals; a scheduled weather cycle could
    otherwise incur repeated charges. Weather collection and sourced,
    approval-gated drafts remain available without a generative AI API.
    """
    return []

def run_daily_cycle():
    from .models import NewsletterSource, NewsletterStory
    # Fail closed before requesting all 31 external forecasts if central owner
    # has not been activated. Never revive a retired specialist Agent.
    agent = require_canonical_content_owner()
    data = province_forecast(7)
    if len(data) != len(PROVINCES) or any(len(item.get('forecast', [])) != 7 for item in data):
        raise RuntimeError('Incomplete seven-day weather forecast; publication withheld')
    report = build_public_report(data)
    day = timezone.localdate()
    src, _ = NewsletterSource.objects.get_or_create(url=SOURCE_URL, defaults={'publisher':'MET Norway','title':'MET Norway Locationforecast (CC BY 4.0)','kind':'research'})
    fp = f'weather-iran-{day.isoformat()}'
    story, created = NewsletterStory.objects.get_or_create(fingerprint=fp, defaults={
        'agent':agent,'source':src,'story_type':'report','title':f'گزارش روزانه هواشناسی ایران | {day.isoformat()}',
        'slug':f'weather-iran-{day.isoformat()}','summary':'برآورد پیش‌بینی ۷ روزه مراکز ۳۱ استان با انتساب به MET Norway.',
        'body':report,'author_name':'مجتبی روزگار','event_date':day,'seo_keywords':['هواشناسی ایران','پیش بینی هوا','آب و هوای استان ها','هواشناسی ۷ روزه','مجتبی روزگار'],
        # This capability prepares a sourced daily draft; publication
        # belongs to the existing newsroom approval/release workflow.
        'status':'draft','published_at':None,
    })
    # A rerun must not overwrite an edited/approved/published report.
    # The fingerprint makes collection idempotent for each calendar day.
    # A repeated scheduler invocation must not spend another API request after
    # both daily research items have already been recorded.
    existing_daily_contents = NewsletterStory.objects.filter(
        fingerprint__in=[
            f'weather-daily-content-{day.isoformat()}-1',
            f'weather-daily-content-{day.isoformat()}-2',
        ]
    ).count()
    generated = generate_research_contents(report) if existing_daily_contents < 2 else []
    content_created = 0
    for idx, item in enumerate(generated[:2],1):
        if not isinstance(item, dict) or not item.get('title'): continue
        title=item['title'].strip()
        fp2=f'weather-daily-content-{day.isoformat()}-{idx}'
        _, was_created = NewsletterStory.objects.get_or_create(fingerprint=fp2, defaults={
            'agent':agent,'source':src,'story_type':'report','title':title[:500],
            'slug':f'weather-research-{day.isoformat()}-{idx}','summary':item.get('summary','')[:3000],
            'body':item.get('body',''),'author_name':'مجتبی روزگار','event_date':day,
            'seo_keywords':item.get('keywords',[]) if isinstance(item.get('keywords',[]),list) else [],
            # LLM output is never auto-published merely because generation
            # was separately authorized; editorial approval is independent.
            'status':'draft','published_at':None,
        })
        content_created += int(was_created)
    return {'date':str(day),'provinces':len(data),'weather_story_id':story.id,'weather_created':created,'research_contents_created':content_created}

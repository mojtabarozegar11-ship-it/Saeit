import json
import os
from datetime import date, timedelta
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from openai import OpenAI

PROVINCES = [
 ('آذربایجان شرقی','تبریز',38.0962,46.2738),('آذربایجان غربی','ارومیه',37.5527,45.0761),('اردبیل','اردبیل',38.2498,48.2933),('اصفهان','اصفهان',32.6546,51.6680),('البرز','کرج',35.8400,50.9391),('ایلام','ایلام',33.6374,46.4227),('بوشهر','بوشهر',28.9234,50.8203),('تهران','تهران',35.6892,51.3890),('چهارمحال و بختیاری','شهرکرد',32.3256,50.8644),('خراسان جنوبی','بیرجند',32.8663,59.2211),('خراسان رضوی','مشهد',36.2605,59.6168),('خراسان شمالی','بجنورد',37.4750,57.3333),('خوزستان','اهواز',31.3183,48.6706),('زنجان','زنجان',36.6736,48.4787),('سمنان','سمنان',35.5729,53.3971),('سیستان و بلوچستان','زاهدان',29.4963,60.8629),('فارس','شیراز',29.5918,52.5837),('قزوین','قزوین',36.2688,50.0041),('قم','قم',34.6416,50.8746),('کردستان','سنندج',35.3219,46.9862),('کرمان','کرمان',30.2839,57.0834),('کرمانشاه','کرمانشاه',34.3142,47.0650),('کهگیلویه و بویراحمد','یاسوج',30.6682,51.5880),('گلستان','گرگان',36.8456,54.4393),('گیلان','رشت',37.2808,49.5832),('لرستان','خرم‌آباد',33.4878,48.3558),('مازندران','ساری',36.5633,53.0601),('مرکزی','اراک',34.0917,49.6892),('هرمزگان','بندرعباس',27.1832,56.2666),('همدان','همدان',34.7980,48.5146),('یزد','یزد',31.8974,54.3569),
]
MODELS = ('ecmwf_ifs025','gfs_seamless','icon_seamless')
SOURCE_URL = 'https://open-meteo.com/'
SOURCE_ECMWF = 'https://www.ecmwf.int/en/forecasts/datasets/open-data'
SOURCE_WMO = 'https://wmo.int/'


def _fetch(lat, lon, days=7):
    params = urlencode({
        'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code',
        'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max',
        'timezone': 'Asia/Tehran', 'forecast_days': days,
        'models': ','.join(MODELS),
    })
    req = Request('https://api.open-meteo.com/v1/forecast?' + params, headers={'User-Agent':'Zomorodmelal-WeatherAgent/1.0'})
    with urlopen(req, timeout=12) as response:
        return json.load(response)


def _avg(d, prefix, i):
    vals = [d.get(f'{prefix}_{m}', [None])[i] for m in MODELS]
    vals = [float(v) for v in vals if v is not None]
    return round(mean(vals), 1) if vals else None


def _model_values(d, prefix, i):
    return {m: d.get(f'{prefix}_{m}', [None] * len(d.get('time', [])))[i] for m in MODELS}


def _risk_flags(day):
    flags=[]
    if day.get('max_c') is not None and day['max_c'] >= 40: flags.append('گرمای شدید')
    if day.get('min_c') is not None and day['min_c'] <= 0: flags.append('سرمای یخبندان')
    if day.get('rain_mm') is not None and day['rain_mm'] >= 25: flags.append('بارش قابل توجه')
    if day.get('wind_kmh') is not None and day['wind_kmh'] >= 50: flags.append('باد شدید')
    return flags


def _consensus_quality(d, i):
    fields=('temperature_2m_max','temperature_2m_min','precipitation_probability_max','precipitation_sum','wind_speed_10m_max')
    total=0; agreement=0
    for prefix in fields:
        vals=[v for v in _model_values(d,prefix,i).values() if v is not None]
        if vals:
            total += 1
            if len(vals) >= 2:
                spread=max(vals)-min(vals)
                agreement += 1 if (prefix.startswith('temperature') and spread <= 3) or (prefix.startswith('wind') and spread <= 12) or (prefix.startswith('precipitation') and spread <= max(10,mean(vals)*0.5)) else 0
    return round(100*agreement/total) if total else 0


def province_forecast(days=7):
    output = []
    for name, capital, lat, lon in PROVINCES:
        raw = _fetch(lat, lon, days)
        d = raw['daily']
        forecast = []
        for i, day in enumerate(d['time']):
            forecast.append({
                'date': day,
                'min_c': _avg(d, 'temperature_2m_min', i),
                'max_c': _avg(d, 'temperature_2m_max', i),
                'rain_probability': _avg(d, 'precipitation_probability_max', i),
                'rain_mm': _avg(d, 'precipitation_sum', i),
                'wind_kmh': _avg(d, 'wind_speed_10m_max', i),
                'model_agreement': _consensus_quality(d, i),
            })
        output.append({'province':name,'capital':capital,'latitude':lat,'longitude':lon,'timezone':raw.get('timezone'),'current':raw.get('current',{}),'forecast':forecast,'data_source_models':list(MODELS)})
    return output


def build_public_report(data):
    today = timezone.localdate().isoformat()
    lines = [f'گزارش روزانه هواشناسی ایران — {today}', '', 'این گزارش برای ۳۱ استان ایران بر پایه پیش‌بینی چندمدلی تهیه شده است. مقادیر روزانه با ترکیب خروجی ECMWF IFS، NOAA GFS و DWD ICON محاسبه شده‌اند.']
    for item in data:
        p = item['forecast'][0]
        flags='، '.join(_risk_flags(p)) or 'بدون پرچم هشدار خودکار'
        lines.append(f"• {item['province']} ({item['capital']}): {p['min_c']} تا {p['max_c']}°C، احتمال بارش {p['rain_probability']}٪، بارش برآوردی {p['rain_mm']} میلی‌متر، باد تا {p['wind_kmh']} km/h، همگرایی مدل‌ها {p['model_agreement']}٪؛ {flags}")
    lines += ['', f'منابع داده: Open-Meteo ({SOURCE_URL})، ECMWF Open Data ({SOURCE_ECMWF})؛ چارچوب ارتباط عدم‌قطعیت و پیش‌بینی چندمدلی با توصیه‌های WMO هم‌راستا است ({SOURCE_WMO}).', 'این گزارش پیش‌بینی مدل‌محور است و جایگزین هشدارها و اطلاعیه‌های رسمی سازمان هواشناسی کشور نیست.']
    return '\n'.join(lines)


def generate_research_contents(weather_summary):
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return [
            {
                'title':'چگونه پیش‌بینی چندمدلی هواشناسی را برای کشاورزی و برنامه‌ریزی بخوانیم؟',
                'summary':'راهنمای پژوهش‌محور برای استفاده از دما، بارش و باد در تصمیم‌های روزمره و کشاورزی.',
                'body':'''پیش‌بینی هوا یک عدد قطعی نیست؛ مجموعه‌ای از برآوردهاست که با گذشت زمان به‌روزرسانی می‌شود. در این سامانه، خروجی مدل‌های ECMWF IFS، NOAA GFS و DWD ICON کنار هم قرار می‌گیرند تا کاربر به‌جای تکیه بر یک مدل، تصویر مقایسه‌ای از وضعیت احتمالی داشته باشد.

برای کشاورزی، سه شاخص را هم‌زمان بخوانید: کمینه و بیشینه دما برای مدیریت تنش گرمایی و سرمایی، احتمال و مقدار بارش برای برنامه‌ریزی آبیاری و عملیات مزرعه، و سرعت باد برای زمان‌بندی سم‌پاشی، محلول‌پاشی، برداشت و عملیات مکانیکی.

هرچه فاصله زمانی پیش‌بینی بیشتر شود، عدم‌قطعیت نیز اهمیت بیشتری پیدا می‌کند. بنابراین تصمیم‌های حساس باید با آخرین به‌روزرسانی، هشدارهای رسمی و شرایط واقعی محل تطبیق داده شوند.

منابع: https://www.ecmwf.int/en/forecasts/datasets/open-data | https://open-meteo.com/en/docs | https://wmo.int/activities/world-weather-research-programme-wwrp''',
                'meta_description':'راهنمای کاربردی استفاده از پیش‌بینی چندمدلی هواشناسی برای کشاورزی، آبیاری، عملیات مزرعه و برنامه‌ریزی.',
                'keywords':['پیش بینی هواشناسی','هواشناسی کشاورزی','ECMWF','GFS','ICON','مدیریت آبیاری','هواشناسی ایران']
            },
            {
                'title':'آموزش عملی تفسیر احتمال بارش، دما و باد در پیش‌بینی هوا',
                'summary':'آموزش ساده و علمی برای تبدیل داده‌های هواشناسی به تصمیم‌های کاربردی.',
                'body':'''احتمال بارش به معنی مقدار بارش نیست؛ این دو شاخص باید جداگانه خوانده شوند. احتمال بارش نشان می‌دهد وقوع بارش در یک بازه چقدر محتمل است، در حالی که مقدار بارش، حجم مورد انتظار را توصیف می‌کند. برای تصمیم‌گیری بهتر، هر دو را همراه با زمان و مکان بررسی کنید.

دما نیز فقط با میانگین روزانه معنا پیدا نمی‌کند. کمینه شبانه و بیشینه روزانه برای کشاورزی، سفر، سلامت، مصرف انرژی و برنامه‌ریزی عملیات اهمیت متفاوتی دارند. باد هم باید همراه با سرعت و زمان وقوع آن بررسی شود؛ زیرا افزایش باد می‌تواند اجرای برخی عملیات بیرونی را محدود کند.

اصل آموزشی مهم این است: یک عدد را به‌تنهایی مبنای تصمیم حساس قرار ندهید. روند چندروزه، مقایسه مدل‌ها، آخرین به‌روزرسانی و هشدارهای رسمی را کنار هم ببینید. این روش با اصول WMO درباره ارتباط عدم‌قطعیت پیش‌بینی هم‌راستا است.

منابع: https://wmo.int/resources/wmo-bulletin-vol-73-2-2024/imo-prize-lecture-2024-ensemble-weather-and-climate-prediction-from-origins-ai | https://open-meteo.com/en/docs''',
                'meta_description':'آموزش تفسیر احتمال بارش، مقدار بارش، دما و باد برای تصمیم‌گیری بهتر در سفر، کشاورزی و زندگی روزمره.',
                'keywords':['آموزش هواشناسی','احتمال بارش','دمای هوا','سرعت باد','پیش بینی هوا','هواشناسی کاربردی']
            }
        ]
    client = OpenAI(api_key=key)
    prompt = f'''دو محتوای فارسی مستقل و حرفه‌ای برای وب‌سایت Zomorodmelal تولید کن؛ نویسنده هر دو «مجتبی روزگار، محقق و پژوهشگر» باشد. یکی درباره «تحقیقات، فناوری و نوآوری کاربردی» و دیگری درباره «آموزش و تحلیل کاربردی برای تصمیم‌گیری». محتواها علمی، قابل بررسی، غیرتبلیغاتی، کاربردی و مناسب SEO باشند. برای هر محتوا JSON با title, summary, body, meta_description, keywords, sources بده. از ادعا یا منبع ساختگی خودداری کن. اگر داده‌ای نیازمند منبع است، فقط از منابع رسمی و معتبر استفاده کن. زمینه امروز: {weather_summary[:4000]}'''
    response = client.chat.completions.create(
        model=os.getenv('OPENAI_WEATHER_CONTENT_MODEL', os.getenv('OPENAI_CHAT_MODEL','gpt-5.6')),
        response_format={'type':'json_object'},
        messages=[
            {'role':'system','content':'تو سردبیر علمی و SEO هستی. جعل منبع و ادعای تأییدنشده ممنوع است.'},
            {'role':'user','content':prompt},
        ],
    )
    obj = json.loads(response.choices[0].message.content or '{}')
    return obj.get('contents', obj if isinstance(obj, list) else [])


def run_daily_cycle():
    from .models import Agent, NewsletterSource, NewsletterStory
    data = province_forecast(7)
    report = build_public_report(data)
    day = timezone.localdate()
    agent = Agent.objects.filter(code='content-research', active=True).first() or Agent.objects.filter(active=True).first()
    if not agent:
        raise RuntimeError('No active content agent')
    src, _ = NewsletterSource.objects.get_or_create(url=SOURCE_URL, defaults={'publisher':'Open-Meteo','title':'Open-Meteo Weather Data','kind':'research'})
    fp = f'weather-iran-{day.isoformat()}'
    story, created = NewsletterStory.objects.get_or_create(fingerprint=fp, defaults={
        'agent':agent,'source':src,'story_type':'report','title':f'گزارش روزانه هواشناسی ایران | {day.isoformat()}',
        'slug':f'weather-iran-{day.isoformat()}','summary':'پیش‌بینی چندمدلی ۷ روزه برای ۳۱ استان ایران.',
        'body':report,'author_name':'مجتبی روزگار','event_date':day,'seo_keywords':['هواشناسی ایران','پیش بینی هوا','آب و هوای استان ها','هواشناسی ۷ روزه','مجتبی روزگار'],
        'status':'published','published_at':timezone.now(),
    })
    if not created:
        story.body=report; story.status='published'; story.published_at=timezone.now(); story.save(update_fields=['body','status','published_at','updated_at'])
    generated = generate_research_contents(report)
    for idx, item in enumerate(generated[:2],1):
        if not isinstance(item, dict) or not item.get('title'): continue
        title=item['title'].strip()
        fp2=f'weather-daily-content-{day.isoformat()}-{idx}'
        NewsletterStory.objects.get_or_create(fingerprint=fp2, defaults={
            'agent':agent,'source':src,'story_type':'report','title':title[:500],
            'slug':f'weather-research-{day.isoformat()}-{idx}','summary':item.get('summary','')[:3000],
            'body':item.get('body',''),'author_name':'مجتبی روزگار','event_date':day,
            'seo_keywords':item.get('keywords',[]) if isinstance(item.get('keywords',[]),list) else [],
            'status':'published','published_at':timezone.now(),
        })
    return {'date':str(day),'provinces':len(data),'weather_story_id':story.id,'research_contents':min(2,len(generated))}

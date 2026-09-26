from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .weather_agent import _fetch, _avg, _risk_flags, _consensus_quality, PROVINCES, MODELS


def weather(request):
    return render(request, "core/weather.html")


def _province_item(item):
    name, capital, lat, lon = item
    raw = _fetch(lat, lon, 7)
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
    for day in forecast: day['risk_flags'] = _risk_flags(day)
    current = raw.get('current',{})
    return {'province':name,'capital':capital,'latitude':lat,'longitude':lon,'current':current,'forecast':forecast,'risk_flags':forecast[0]['risk_flags'],'data_source_models':list(MODELS)}


@require_GET
def weather_api(request):
    cached = cache.get('weather_iran_provinces_v3')
    if cached:
        return JsonResponse(cached)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs=[pool.submit(_province_item,item) for item in PROVINCES]
        for job in as_completed(jobs):
            try: results.append(job.result())
            except Exception: pass
    results.sort(key=lambda x:x['province'])
    if len(results) < len(PROVINCES):
        return JsonResponse({'status':'degraded','message':'Some provincial forecasts are temporarily unavailable.','provinces':results,'expected_provinces':len(PROVINCES)},status=503)
    payload={'status':'ok','source':'Open-Meteo / ECMWF IFS + NOAA GFS + DWD ICON','models':list(MODELS),'provinces':results,'province_count':len(results)}
    cache.set('weather_iran_provinces_v3',payload,900)
    return JsonResponse(payload)

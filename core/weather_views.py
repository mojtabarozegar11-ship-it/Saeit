from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .met_weather_adapter import SOURCE_MODEL, normalize_locationforecast
from .weather_agent import _fetch, _risk_flags, PROVINCES, SOURCE_ATTRIBUTION, SOURCE_LICENSE, SOURCE_URL


def weather(request):
    return render(request, "core/weather.html")


def _province_item(item):
    name, capital, lat, lon = item
    raw = _fetch(lat, lon, 7)
    parsed = normalize_locationforecast(raw, days=7)
    forecast = parsed['forecast']
    for day in forecast: day['risk_flags'] = _risk_flags(day)
    return {'province':name,'capital':capital,'latitude':lat,'longitude':lon,**parsed,'risk_flags':forecast[0]['risk_flags'],'data_source_models':[SOURCE_MODEL]}


@require_GET
def weather_api(request):
    cache_key = 'weather_iran_provinces_met_norway_v1'
    cached = cache.get(cache_key)
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
    payload={'status':'ok','source':SOURCE_ATTRIBUTION,'source_url':SOURCE_URL,'license_url':SOURCE_LICENSE,'models':[SOURCE_MODEL],'provinces':results,'province_count':len(results)}
    # Coordinate payloads are cached separately until their MET Expires time.
    cache.set(cache_key,payload,60)
    return JsonResponse(payload)

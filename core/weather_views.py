[Reading 33 lines from start (total: 33 lines, 0 remaining)]

import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def weather(request):
    return render(request, "core/weather.html")


@require_GET
def weather_api(request):
    try:
        lat = float(request.GET.get("lat", "35.6892"))
        lon = float(request.GET.get("lon", "51.3890"))
    except ValueError:
        return JsonResponse({"status": "error", "message": "Invalid coordinates"}, status=400)
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return JsonResponse({"status": "error", "message": "Invalid coordinates"}, status=400)
    query = urlencode({
        "latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 5,
    })
    try:
        with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=5) as response:
            data = json.load(response)
    except Exception as exc:
        return JsonResponse({"status": "degraded", "message": exc.__class__.__name__}, status=503)
    return JsonResponse({"status": "ok", "source": "Open-Meteo", "data": data})

[executed on device: zohal.pws-dns.net (457d9cac-c176-4c0a-a847-08fb0f2007dc)]
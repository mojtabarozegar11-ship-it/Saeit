"""Convert MET Norway Locationforecast 2.0 into honest local daily estimates.

This module is independent of Django so that production payload parsing can be
checked without a database or an external weather API request.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


TEHRAN = ZoneInfo('Asia/Tehran')
SOURCE_MODEL = 'MET Norway Locationforecast 2.0'


def _number(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _symbol_description(symbol):
    if not isinstance(symbol, str):
        return 'وضعیت نامشخص'
    if symbol.startswith('clearsky'):
        return 'صاف'
    if symbol.startswith('fair'):
        return 'عمدتاً صاف'
    if symbol.startswith('partlycloudy'):
        return 'نیمه‌ابری'
    if symbol.startswith('cloudy'):
        return 'ابری'
    if 'thunder' in symbol:
        return 'احتمال رعدوبرق'
    if 'snow' in symbol:
        return 'احتمال برف'
    if 'sleet' in symbol:
        return 'احتمال برف و باران'
    if 'rain' in symbol:
        return 'احتمال باران'
    if 'fog' in symbol:
        return 'مه'
    return 'وضعیت متغیر'


def normalize_locationforecast(payload, *, days=7, start_date=None):
    """Return forecast for a local date range, or fail closed on missing days.

    Rain is apportioned uniformly over the provider's 1/6/12-hour intervals
    when they cross midnight. This is an approximation, not a measurement.
    Do not invent a precipitation probability when MET does not provide one.
    """
    if not isinstance(days, int) or not 1 <= days <= 9:
        raise ValueError('Forecast days must be between 1 and 9')
    if start_date is None:
        start_date = datetime.now(TEHRAN).date()
    raw_series = payload.get('properties', {}).get('timeseries', [])
    if not isinstance(raw_series, list) or not raw_series:
        raise ValueError('Missing MET Norway timeseries')

    wanted = {start_date + timedelta(days=n) for n in range(days)}
    buckets = defaultdict(lambda: {'temperature': [], 'wind': [], 'rain': [], 'probability': []})
    current = None

    for entry in raw_series:
        if not isinstance(entry, dict):
            continue
        try:
            forecast_at = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
            if forecast_at.tzinfo is None:
                continue
            local_at = forecast_at.astimezone(TEHRAN)
        except (KeyError, AttributeError, ValueError, TypeError):
            continue
        datum = entry.get('data', {})
        details = datum.get('instant', {}).get('details', {})
        temperature = _number(details.get('air_temperature'))
        wind = _number(details.get('wind_speed'))
        humidity = _number(details.get('relative_humidity'))
        local_day = local_at.date()

        next_period = next(
            ((hours, datum[key]) for hours, key in ((1, 'next_1_hours'), (6, 'next_6_hours'), (12, 'next_12_hours'))
             if isinstance(datum.get(key), dict)),
            None,
        )
        symbol = next_period[1].get('summary', {}).get('symbol_code') if next_period else None
        if current is None:
            current = {
                'temperature_2m': round(temperature, 1) if temperature is not None else None,
                'relative_humidity_2m': round(humidity) if humidity is not None else None,
                'wind_speed_10m': round(wind * 3.6, 1) if wind is not None else None,
                'description': _symbol_description(symbol),
                'forecast_time': local_at.isoformat(),
            }
        if local_day in wanted:
            if temperature is not None:
                buckets[local_day]['temperature'].append(temperature)
            if wind is not None:
                buckets[local_day]['wind'].append(wind * 3.6)

        if not next_period:
            continue
        hours, period = next_period
        period_details = period.get('details', {})
        rain = _number(period_details.get('precipitation_amount'))
        probability = _number(period_details.get('probability_of_precipitation'))
        # MET's forecast period starts at entry.time; 6/12-hour amounts can
        # cross the Iranian midnight. Apportion approximately by hour.
        for hour in range(hours):
            period_day = (local_at + timedelta(hours=hour)).date()
            if period_day not in wanted:
                continue
            if rain is not None:
                buckets[period_day]['rain'].append(max(0.0, rain) / hours)
            if probability is not None:
                buckets[period_day]['probability'].append(max(0.0, min(100.0, probability)))

    forecast = []
    for day in sorted(wanted):
        bucket = buckets[day]
        if not bucket['temperature']:
            raise ValueError(f'Incomplete MET Norway forecast: {day.isoformat()}')
        forecast.append({
            'date': day.isoformat(),
            'min_c': round(min(bucket['temperature']), 1),
            'max_c': round(max(bucket['temperature']), 1),
            'rain_probability': round(max(bucket['probability'])) if bucket['probability'] else None,
            'rain_mm': round(sum(bucket['rain']), 1) if bucket['rain'] else None,
            'wind_kmh': round(max(bucket['wind']), 1) if bucket['wind'] else None,
        })
    if current is None:
        raise ValueError('No valid MET Norway forecast timestamps')
    return {'timezone': 'Asia/Tehran', 'current': current, 'forecast': forecast}

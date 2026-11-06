"""Offline checks for the real MET Norway Locationforecast response shape."""

import unittest
from datetime import date, datetime, timedelta, timezone

from core.met_weather_adapter import normalize_locationforecast


def _entry(at, *, temp=21, wind=4, rain=0.5, probability=None, period=1):
    details = {'precipitation_amount': rain}
    if probability is not None:
        details['probability_of_precipitation'] = probability
    return {
        'time': at.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'data': {
            'instant': {'details': {
                'air_temperature': temp,
                'wind_speed': wind,
                'relative_humidity': 55,
            }},
            f'next_{period}_hours': {
                'summary': {'symbol_code': 'partlycloudy_day'},
                'details': details,
            },
        },
    }


class MetWeatherAdapterTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 11, 6)
        self.utc_start = datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc)

    def _payload(self, length=8):
        entries = [_entry(self.utc_start + timedelta(hours=hour), temp=10 + hour % 15)
                   for hour in range(length * 24)]
        return {'properties': {'timeseries': entries}}

    def test_seven_local_days_and_conversions(self):
        output = normalize_locationforecast(self._payload(), days=7, start_date=self.start)
        self.assertEqual(len(output['forecast']), 7)
        self.assertEqual(output['forecast'][0]['date'], '2026-11-06')
        self.assertEqual(output['timezone'], 'Asia/Tehran')
        self.assertEqual(output['current']['wind_speed_10m'], 14.4)
        self.assertEqual(output['current']['description'], 'نیمه‌ابری')
        self.assertEqual(output['current']['relative_humidity_2m'], 55)
        self.assertGreater(output['forecast'][0]['rain_mm'], 0)
        self.assertEqual(output['forecast'][0]['rain_probability'], None)

    def test_probability_is_not_assumed_to_be_zero(self):
        payload = self._payload()
        payload['properties']['timeseries'][2]['data']['next_1_hours']['details']['probability_of_precipitation'] = 80
        output = normalize_locationforecast(payload, start_date=self.start)
        self.assertEqual(output['forecast'][0]['rain_probability'], 80)
        self.assertIsNone(output['forecast'][1]['rain_probability'])

    def test_six_hour_precipitation_crosses_tehran_midnight(self):
        # 18:00 UTC is 21:30 Asia/Tehran in November, with three hours
        # before and three hours after the local midnight.
        period = _entry(datetime(2026, 11, 6, 18, tzinfo=timezone.utc), rain=6.0, period=6)
        other = [_entry(self.utc_start + timedelta(days=day), rain=None)
                 for day in range(8)]
        payload = {'properties': {'timeseries': other + [period]}}
        result = normalize_locationforecast(payload, start_date=self.start)
        self.assertEqual(result['forecast'][0]['rain_mm'], 3.0)
        self.assertEqual(result['forecast'][1]['rain_mm'], 3.0)

    def test_missing_day_is_rejected(self):
        payload = {'properties': {'timeseries': [_entry(self.utc_start)]}}
        with self.assertRaisesRegex(ValueError, 'Incomplete MET Norway forecast'):
            normalize_locationforecast(payload, start_date=self.start)

    def test_missing_data_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing MET Norway timeseries'):
            normalize_locationforecast({'properties': {}}, start_date=self.start)

    def test_invalid_days_are_rejected(self):
        for count in (0, 10, 7.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                normalize_locationforecast(self._payload(), days=count, start_date=self.start)

    def test_nan_is_not_reported_as_a_temperature(self):
        payload = self._payload()
        for entry in payload['properties']['timeseries']:
            entry['data']['instant']['details']['air_temperature'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Incomplete MET Norway forecast'):
            normalize_locationforecast(payload, start_date=self.start)

    def test_wind_and_temperature_extrema(self):
        payload = self._payload()
        payload['properties']['timeseries'][1]['data']['instant']['details']['wind_speed'] = 25.0
        payload['properties']['timeseries'][1]['data']['instant']['details']['air_temperature'] = -2.0
        output = normalize_locationforecast(payload, start_date=self.start)
        self.assertEqual(output['forecast'][0]['wind_kmh'], 90.0)
        self.assertEqual(output['forecast'][0]['min_c'], -2.0)


if __name__ == '__main__':
    unittest.main()

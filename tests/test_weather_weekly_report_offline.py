"""Ensure public weather editorial text actually includes all seven dates."""

import unittest

from core.weather_weekly_report import render_seven_day_report


def province(days=7, missing_rain=False):
    dates = [f"2026-11-{day:02d}" for day in range(8, 8 + days)]
    return {
        "province": "گیلان", "capital": "رشت",
        "forecast": [
            {"date": day, "min_c": 8, "max_c": 15,
             "rain_mm": None if missing_rain else 2.0,
             "wind_kmh": 20.0, "rain_probability": None}
            for day in dates
        ],
    }


def render(items):
    return render_seven_day_report(
        items, report_date="2026-11-08", flags_for_day=lambda d: [],
        attribution="MET Norway", source_url="https://api.met.no/weatherapi/locationforecast/2.0/",
        license_url="https://creativecommons.org/licenses/by/4.0/",
    )


class WeatherWeeklyReportTests(unittest.TestCase):
    def test_all_seven_days_in_public_body(self):
        text = render([province()])
        for day in range(8, 15):
            self.assertIn(f"2026-11-{day:02d}", text)
        self.assertIn("14.0 میلی‌متر", text)
        self.assertIn("احتمال بارش ناموجود", text)
        self.assertTrue(text.endswith("\n\n#مجتبی_روزگار"))

    def test_short_six_day_record_is_rejected(self):
        with self.assertRaises(ValueError):
            render([province(days=6)])

    def test_unknown_rain_not_reported_as_zero(self):
        text = render([province(missing_rain=True)])
        self.assertIn("ناموجود (داده ناقص)", text)

    def test_repeated_day_is_rejected(self):
        item = province()
        item["forecast"][1]["date"] = item["forecast"][0]["date"]
        with self.assertRaises(ValueError):
            render([item])

    def test_skipped_calendar_day_is_rejected(self):
        item = province()
        item["forecast"][4]["date"] = "2026-11-17"
        with self.assertRaisesRegex(ValueError, "consecutive"):
            render([item])

    def test_duplicate_provinces_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            render([province(), province()])

    def test_impossible_temperatures_and_negative_rain_rejected(self):
        for change in ({"min_c": 30, "max_c": 12}, {"rain_mm": -1}):
            with self.subTest(change=change):
                item = province()
                item["forecast"][0].update(change)
                with self.assertRaises(ValueError):
                    render([item])

    def test_invalid_probability_and_nan_rejected(self):
        for change in ({"rain_probability": 101}, {"wind_kmh": float("nan")}):
            with self.subTest(change=change):
                item = province()
                item["forecast"][0].update(change)
                with self.assertRaises(ValueError):
                    render([item])


if __name__ == "__main__":
    unittest.main()

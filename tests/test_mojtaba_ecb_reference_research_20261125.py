from datetime import date, datetime, timezone, timedelta
from unittest import TestCase

from services.mojtaba_ecb_reference_research import (
    parse_rates, build_research, SourceRejected, CURRENCIES, NS, NOTICE,
)


def example():
    dates = ("2026-11-24", "2026-11-23", "2026-11-20",
             "2026-11-19", "2026-11-18", "2026-11-17")
    ns = NS[1:-1]
    return ('<Cube xmlns="' + ns + '">' + ''.join(
        '<Cube time="' + day + '">' + ''.join(
            '<Cube currency="' + currency + '" rate="' + str(index + 1) + '"/>'
            for currency in CURRENCIES) + '</Cube>'
        for index, day in enumerate(dates)) + '</Cube>').encode()


class ECBResearchTests(TestCase):
    def test_parse_reference_dates_and_identify_information_only(self):
        data = example()
        latest, prior, current, previous = parse_rates(data, today=date(2026, 11, 25))
        self.assertEqual(latest, date(2026, 11, 24))
        self.assertEqual(prior, date(2026, 11, 17))
        moment = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
        record = build_research(data, retrieved_at=moment,
                                reviewed_at=moment + timedelta(minutes=10),
                                reviewer_id="reviewer")
        self.assertIn(NOTICE, record.scenario)
        self.assertIn("EUR/USD: 1 (-83.33%", record.scenario)

    def test_stale_duplicate_and_incomplete_data_rejected(self):
        for data, today in (
            (example(), date(2026, 12, 1)),
            (example().replace(b'2026-11-23', b'2026-11-24'), date(2026, 11, 25)),
            (example().replace(b'currency="USD"', b'currency="XXX"'), date(2026, 11, 25)),
            (b'<!DOCTYPE x><x/>', date(2026, 11, 25)),
        ):
            with self.subTest(today=today), self.assertRaises(SourceRejected):
                parse_rates(data, today=today)

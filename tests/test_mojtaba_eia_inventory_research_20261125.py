from datetime import date, datetime, timezone, timedelta
from unittest import TestCase
from services.mojtaba_eia_inventory_research import (
    parse_inventory, build_research, SourceRejected, TITLE,
)


def fixture():
    cells = ["2026-Nov", "11/06", "410,000", "11/13", "412,000",
             "11/20", "408,000", "", "", "", ""]
    return ("<h1>" + TITLE + "</h1><table><tr>" +
            "".join("<td>" + cell + "</td>" for cell in cells) +
            "</tr></table>").encode()


class EIAResearchTests(TestCase):
    def test_inventory_change_and_units(self):
        data = fixture()
        self.assertEqual(parse_inventory(data, today=date(2026, 11, 25)),
                         (date(2026, 11, 20), date(2026, 11, 13), 408000, 412000))
        now = datetime(2026, 11, 25, 10, tzinfo=timezone.utc)
        record = build_research(data, retrieved_at=now,
                                reviewed_at=now+timedelta(minutes=2),
                                reviewer_id="reviewer")
        self.assertIn("-4,000 thousand barrels", record.scenario)
        self.assertIn("not a spot or futures quote", record.scenario)

    def test_wrong_series_stale_and_missing_observation_denied(self):
        for data, today in (
            (fixture().replace(TITLE.encode(), b"Unrelated price series"), date(2026, 11, 25)),
            (fixture(), date(2026, 12, 10)),
            (fixture().replace(b"11/13", b"11/06"), date(2026, 11, 25)),
            (fixture().replace(b"412,000", b"NA"), date(2026, 11, 25)),
        ):
            with self.subTest(today=today), self.assertRaises(SourceRejected):
                parse_inventory(data, today=today)

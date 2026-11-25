"""EIA commercial crude inventory fundamentals, not licensed spot-price resale."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
import re
from urllib.request import Request, build_opener

from services.mojtaba_ecb_reference_research import NoRedirect
from services.mojtaba_signal_policy import EducationalSignal, RISK_DISCLAIMER

SOURCE_URL = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=WCESTUS1"
RIGHTS_URL = "https://www.eia.gov/about/copyrights_reuse.php"
TITLE = "Weekly U.S. Ending Stocks excluding SPR of Crude Oil (Thousand Barrels)"
MAX_BYTES = 4_000_000
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class SourceRejected(ValueError):
    pass


class Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.title_seen = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
            self.cell = None
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if TITLE.casefold() in data.casefold():
            self.title_seen = True
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.row is not None and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
            self.cell = None


def fetch_eia_bytes():
    req = Request(SOURCE_URL, headers={"User-Agent": "MojtabaResearch/1.0"})
    with build_opener(NoRedirect()).open(req, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
    if not 0 < len(data) <= MAX_BYTES:
        raise SourceRejected("Invalid EIA response size")
    return data


def parse_inventory(data, *, today):
    if type(data) is not bytes or not 0 < len(data) <= MAX_BYTES or type(today) is not date:
        raise SourceRejected("Invalid inventory input")
    parser = Rows()
    parser.feed(data.decode("utf-8", errors="replace"))
    parser.close()
    if not parser.title_seen:
        raise SourceRejected("Incorrect EIA series")
    observations = {}
    for row in parser.rows:
        if not row or not re.fullmatch(r"\d{4}-[A-Z][a-z]{2}", row[0]):
            continue
        year = int(row[0][:4])
        if year not in (today.year, today.year - 1):
            continue
        if len(row) != 11 or row[0][5:] not in MONTHS:
            raise SourceRejected("Unexpected EIA row layout")
        month = MONTHS.index(row[0][5:]) + 1
        for day, value in zip(row[1::2], row[2::2]):
            if not day and not value:
                continue
            if not re.fullmatch(r"\d{2}/\d{2}", day):
                raise SourceRejected("Malformed inventory observation date")
            if value in ("", "-", "--", "NA", "W"):
                continue
            if not re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", value):
                raise SourceRejected("Malformed inventory observation")
            try:
                when = date(year, int(day[:2]), int(day[3:]))
            except ValueError as exc:
                raise SourceRejected("Invalid inventory observation date") from exc
            amount = int(value.replace(",", ""))
            if (when.month != month or when > today or when in observations
                    or not 0 < amount < 2_000_000):
                raise SourceRejected("Invalid or duplicate inventory observation")
            observations[when] = amount
    dates = sorted(observations, reverse=True)
    if len(dates) < 2 or today - dates[0] > timedelta(days=14):
        raise SourceRejected("Missing or stale inventory data")
    if dates[0] - dates[1] != timedelta(days=7):
        raise SourceRejected("Missing consecutive weekly inventory observations")
    return dates[0], dates[1], observations[dates[0]], observations[dates[1]]


def build_research(data, *, retrieved_at, reviewed_at, reviewer_id):
    if (type(retrieved_at) is not datetime or retrieved_at.utcoffset() is None
            or type(reviewed_at) is not datetime or reviewed_at.utcoffset() is None
            or not retrieved_at <= reviewed_at <= retrieved_at + timedelta(hours=24)):
        raise SourceRejected("Actual retrieval and subsequent review required")
    retrieved_at = retrieved_at.astimezone(timezone.utc)
    reviewed_at = reviewed_at.astimezone(timezone.utc)
    latest, prior, current, previous = parse_inventory(data, today=retrieved_at.date())
    delta = current - previous
    pct = Decimal(delta) / Decimal(previous) * 100
    scenario = (
        f"Source: U.S. Energy Information Administration (EIA), WCESTUS1, "
        f"week ending {latest.isoformat()}: {current:,} thousand barrels of US "
        f"crude oil stocks excluding the Strategic Petroleum Reserve, versus "
        f"{previous:,} on {prior.isoformat()}. Change: {delta:+,} thousand barrels "
        f"({pct:+.2f}%, Mojtaba.bot.ai calculation). Inventory changes are one "
        f"fundamental indicator; this is not a spot or futures quote. "
        f"Supply, demand, imports, refinery throughput and expectations also matter."
    )
    return EducationalSignal(
        record_id="eia_oil_" + latest.strftime("%Y%m%d"), asset="OIL-INVENTORY",
        timeframe="1w", scenario=scenario,
        invalidation="New inventory releases, revisions or changes in supply and demand "
                     "may invalidate the historical comparison and its interpretation.",
        evidence_url=SOURCE_URL, observed_at=retrieved_at, reviewed_at=reviewed_at,
        reviewer_id=reviewer_id, risk_statement=RISK_DISCLAIMER, as_of=reviewed_at,
    )

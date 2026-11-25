"""Official ECB daily reference-rate research adapter; no trading or paid API.

Rates are information-only, not broker quotes. ECB reuse requires attribution,
pre-purchase notice and a free-source notice whenever buyers access the data.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree as ET

from services.mojtaba_signal_policy import EducationalSignal, RISK_DISCLAIMER

SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
SOURCE_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
RIGHTS_URL = "https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html"
NOTICE = ("Source: European Central Bank (ECB). The original reference rates "
          "are freely available on the ECB website. Percentage changes are "
          "Mojtaba.bot.ai calculations, not ECB figures or executable prices.")
MAX_BYTES = 500_000
CURRENCIES = ("USD", "GBP", "JPY", "CHF", "CAD", "AUD")
NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"


class SourceRejected(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SourceRejected("Unexpected source redirect")


def fetch_ecb_bytes():
    request = Request(SOURCE_URL, headers={"User-Agent": "MojtabaResearch/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        data = response.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise SourceRejected("ECB response size invalid")
    return data


def parse_rates(data, *, today):
    if (type(data) is not bytes or not 0 < len(data) <= MAX_BYTES
            or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper()
            or type(today) is not date):
        raise SourceRejected("Invalid source document")
    try:
        root = ET.fromstring(data)
        rows = {}
        for day in root.iter(NS + "Cube"):
            if "time" not in day.attrib:
                continue
            observed = date.fromisoformat(day.attrib["time"])
            if observed > today or observed in rows:
                raise SourceRejected("Future or duplicate source date")
            rates = {}
            for cell in day.findall(NS + "Cube"):
                currency = cell.attrib.get("currency")
                if currency not in CURRENCIES:
                    continue
                if currency in rates:
                    raise SourceRejected("Duplicate currency")
                value = Decimal(cell.attrib["rate"])
                if not value.is_finite() or not Decimal("0.00001") < value < Decimal("100000"):
                    raise SourceRejected("Invalid exchange rate")
                rates[currency] = value
            if set(rates) != set(CURRENCIES):
                raise SourceRejected("Incomplete reference rates")
            rows[observed] = rates
    except (ET.ParseError, KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise SourceRejected("Malformed reference-rate series") from exc
    dates = sorted(rows, reverse=True)
    if len(dates) < 6 or today - dates[0] > timedelta(days=4):
        raise SourceRejected("Missing or stale reference observations")
    if not timedelta(days=5) <= dates[0] - dates[5] <= timedelta(days=12):
        raise SourceRejected("Unexpected five-observation interval")
    return dates[0], dates[5], rows[dates[0]], rows[dates[5]]


def build_research(data, *, retrieved_at, reviewer_id):
    if (type(retrieved_at) is not datetime or retrieved_at.utcoffset() is None):
        raise SourceRejected("Actual retrieval timestamp required")
    retrieved_at = retrieved_at.astimezone(timezone.utc)
    latest, prior, current, previous = parse_rates(data, today=retrieved_at.date())
    changes = []
    for code in CURRENCIES:
        pct = (current[code] / previous[code] - 1) * 100
        changes.append(f"EUR/{code}: {current[code]} ({pct:+.2f}% over five observations)")
    scenario = (f"ECB reference dates {prior.isoformat()} to {latest.isoformat()}. "
                + "; ".join(changes) + ". " + NOTICE)
    return EducationalSignal(
        record_id="ecb_fx_" + latest.strftime("%Y%m%d"),
        asset="EUR-FX", timeframe="1w", scenario=scenario,
        invalidation="Reference-rate comparisons are historical. A subsequent ECB observation "
                     "or a change in macroeconomic assumptions invalidates extrapolation.",
        evidence_url=SOURCE_PAGE, observed_at=retrieved_at,
        reviewed_at=retrieved_at, reviewer_id=reviewer_id,
        risk_statement=RISK_DISCLAIMER, as_of=retrieved_at,
    )

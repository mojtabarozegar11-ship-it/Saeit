from pathlib import Path


SIGNAL_PAGE = Path(__file__).parents[1] / "templates" / "moj-prop" / "signals" / "index.html"


def test_educational_signal_cta_has_valid_anchor_markup():
    html = SIGNAL_PAGE.read_text(encoding="utf-8")
    assert '<a href="/moj-prop/?service=signals#request">Request educational signals</a>' in html
    assert "Request educational signals/a>" not in html

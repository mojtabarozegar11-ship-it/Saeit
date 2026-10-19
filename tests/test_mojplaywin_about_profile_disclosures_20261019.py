"""Regression checks for MojPlayWin /about/ illustrative profiles.

These checks cover source fragments only; a passing run is not proof that the
isolated, priority-routed production HTML has been re-published.
"""
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1] / "content"


class ProfileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.profile_counts = {"mpw-team-card": 0, "mpw-intl-card": 0, "mpw-advisory-card": 0}
        self.badge_count = 0
        self.image_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set(a.get("class", "").split())
        for key in self.profile_counts:
            if key in classes:
                self.profile_counts[key] += 1
        if "mpw-profile-indicator" in classes:
            self.badge_count += 1
        if tag == "img":
            self.image_count += 1


def _check(filename, profile_class, header_id, header, forbidden):
    source = (ROOT / filename).read_text(encoding="utf-8")
    parser = ProfileParser()
    parser.feed(source)
    assert parser.profile_counts[profile_class] == 10
    assert sum(parser.profile_counts.values()) == 10, "A foreign profile group was introduced"
    assert parser.badge_count == 10, "Each illustrative profile requires a visible disclosure"
    assert parser.image_count >= 1, "Existing portrait gallery must remain"
    assert f'<h2 id="{header_id}">{header}</h2>' in source
    assert forbidden not in source, "A misleading role or organizational heading remains"
    assert source.count("</style>") == 1
    assert source.count("</section>") == 1


def test_about_team_profiles_have_individual_disclosures():
    _check(
        "mojplaywin_about_team_section_20261018.html",
        "mpw-team-card",
        "mpw-meet-team-heading-20261018",
        "Illustrative Team Roles",
        "CEO &amp; Business Development",
    )


def test_international_profiles_do_not_claim_a_second_ceo():
    _check(
        "mpw_international_team_section_20261018.html",
        "mpw-intl-card",
        "mpw-international-team-heading-20261018",
        "Illustrative International Operations Roles",
        ">Chief Executive Officer<",
    )


def test_fictional_advisors_are_not_presented_as_a_real_board():
    _check(
        "mpw_senior_advisory_board_20261018.html",
        "mpw-advisory-card",
        "mpw-senior-advisory-heading-20261018",
        "Illustrative Advisory Role Profiles",
        ">Senior Advisory Board<",
    )

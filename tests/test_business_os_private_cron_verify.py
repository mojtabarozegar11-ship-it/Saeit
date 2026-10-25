"""Synthetic freshness tests; never load or expose live customer readings."""
from datetime import datetime, timedelta, timezone

from scripts.business_os_private_cron_verify import advanced_after_install

NOW = datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)


def test_post_install_report_must_be_later_than_install():
    since = (NOW - timedelta(minutes=8)).timestamp()
    assert advanced_after_install(
        {"generated_at": (NOW - timedelta(minutes=1)).isoformat()}, since, NOW)
    assert not advanced_after_install(
        {"generated_at": (NOW - timedelta(minutes=9)).isoformat()}, since, NOW)


def test_post_install_report_must_be_fresh():
    since = (NOW - timedelta(hours=3)).timestamp()
    assert not advanced_after_install(
        {"generated_at": (NOW - timedelta(minutes=21)).isoformat()}, since, NOW)


def test_post_install_report_rejects_naive_or_future():
    since = (NOW - timedelta(minutes=8)).timestamp()
    assert not advanced_after_install(
        {"generated_at": (NOW + timedelta(minutes=2)).isoformat()}, since, NOW)
    try:
        advanced_after_install({"generated_at": NOW.replace(tzinfo=None).isoformat()},
                               since, NOW)
    except ValueError:
        pass
    else:
        raise AssertionError("naive clock accepted")

"""Regression coverage for the read-only, exact-baseline SEO candidate builder."""
from unittest.mock import patch

import pytest

from scripts import mojprop_seo_exact_live_candidate_20261120 as seo


def fixture(path):
    spec = seo.PAGES[path]
    anchor = spec[4]
    raw = ('<!doctype html><html lang="en"><head><title>Before</title>'
           '<meta name="description" content="Before"></head><body>'
           '<form method="post"><input name="unchanged"></form>'
           + anchor + '</body></html>').encode()
    return raw, (seo.sha(raw), *spec[1:])


@pytest.mark.parametrize("path", tuple(seo.PAGES))
def test_exact_candidate_and_preserved_body(path):
    raw, spec = fixture(path)
    with patch.dict(seo.PAGES, {path: spec}):
        out, receipt = seo.build_candidate(path, raw)
    before, after = raw.split(b"</head>", 1)[1], out.split(b"</head>", 1)[1]
    if spec[4]:
        assert after == before.replace(spec[4].encode(),
            spec[4].encode() + b"\n" + spec[5].encode(), 1)
    else:
        assert after == before
    assert receipt["deployment_authorized"] is False
    assert receipt["before_sha256"] == seo.sha(raw)
    assert receipt["after_sha256"] == seo.sha(out)
    assert b'name="robots" content="index,follow,max-image-preview:large"' in out
    assert b'application/ld+json' in out
    assert out.count(b'rel="canonical"') == 1


@pytest.mark.parametrize("path", tuple(seo.PAGES))
def test_drift_refused(path):
    raw, spec = fixture(path)
    with patch.dict(seo.PAGES, {path: spec}):
        with pytest.raises(ValueError, match="differs"):
            seo.build_candidate(path, raw + b"\n")


@pytest.mark.parametrize("path", ["signals/index.html", "starter-30-trx/index.html", "../index.html", "/index.html"])
def test_out_of_scope_refused(path):
    with pytest.raises(ValueError, match="out of scope"):
        seo.build_candidate(path, b"any")


def test_ambiguous_anchor_refused_even_with_matching_hash():
    path = "index.html"
    raw, spec = fixture(path)
    raw = raw.replace(b"</body>", spec[4].encode() + b"</body>")
    with patch.dict(seo.PAGES, {path: (seo.sha(raw), *spec[1:])}):
        with pytest.raises(ValueError, match="ambiguous CTA"):
            seo.build_candidate(path, raw)

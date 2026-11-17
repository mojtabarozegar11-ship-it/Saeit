#!/usr/bin/env python3
"""C136 deterministic source-only conflict resolution for Moj Prop + main.

This script runs on a temporary GitHub Actions runner after git merge --no-commit
with *pinned* source commits. It preserves existing main payment controls,
routes and live digital-store safeguards, while retaining the canonical
MOJ-PROP-01 consent endpoints and nonpayable disclosure.

NEVER run against a live webroot or user data. It cannot merge to main,
deploy, pay, send mail, create customers, commit or push. Caller owns those
later decisions; this script only reconciles eight already-conflicted files.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

CONFLICT_PATHS = (
    "config/urls.py",
    "core/financial_brand_pages.py",
    "core/mojplaywin_product_detail.py",
    "core/templates/core/financial_brand_page.html",
    "core/tests/test_mpw_store_real_template_render.py",
    "services/mpw_trx_guest_commerce.py",
    "templates/moj-prop-v4/index.html",
    "templates/moj-prop/contact/index.html",
)
MAX_BYTES = 160_000
MAIN_ROUTES = (
    'path("moj-prop-intake/", mojprop_intake',
    'path("moj-prop-status/", mojprop_receipt_status',
    'path("moj-prop-quote/<str:token>/", customer_quote',
    'path("moj-signal-free-subscribe/", signal_free_subscribe',
)
CANONICAL_ROUTES = (
    'path("moj-prop-interest/", moj_prop_interest',
    'path("moj-prop-interest/form/", moj_prop_interest_form',
    'path("moj-prop/", moj_prop_landing',
    'path("moj-prop/dashboard/", moj_prop_dashboard',
)
SOURCE_BANNER = "# C136: keep existing main public intake and add the independent consent-only\n"


def require(text: str, needles: tuple[str, ...], name: str) -> None:
    for needle in needles:
        if needle not in text:
            raise ValueError(f"required {name} guard/anchor missing; abort")


def resolve_source(path: str, main: str, canonical: str) -> str:
    """Pure: choose or compose reviewed business source, fail closed on drift."""
    if path not in CONFLICT_PATHS:
        raise ValueError("unsupported path")
    if not main or not canonical or len(main) > MAX_BYTES or len(canonical) > MAX_BYTES:
        raise ValueError("missing or oversized reviewed source")

    if path == "config/urls.py":
        require(main, MAIN_ROUTES, "main public URL")
        require(canonical, CANONICAL_ROUTES, "canonical opt-in URL")
        assert 'from core.moj_prop_views import ' in canonical
        # Extract only the reviewed canonical tail after the existing blog/news.
        marker = "# Moj Prop is a MojPlayWin-only informational division."
        if canonical.count(marker) != 1 or main.count('urlpatterns += [') < 1:
            raise ValueError("unexpected URL structure")
        tail = canonical[canonical.index(marker):].strip()
        if tail.count('path("moj-prop-interest/form/"') != 1:
            raise ValueError("ambiguous dedicated GET")
        result = main.rstrip() + "\n\n" + SOURCE_BANNER + tail + "\n"
        require(result, MAIN_ROUTES + CANONICAL_ROUTES, "integrated routes")
        if 'path("moj-prop-interest/form/"' not in result:
            raise ValueError("consent form would be unmounted")
        return result

    if path == "core/financial_brand_pages.py":
        require(main, (
            'request.get_host().split(":", 1)[0]',
            "SIGNAL_INTAKE_PATH",
            "SIGNAL_FREE_PREVIEW_PATH",
            'destination_url = SIGNAL_INTAKE_PATH',
        ), "validated host and educational CTAs")
        require(canonical, ("signal_offer = None", "from .signal_commercial_catalog import offer"),
                "canonical nonpayable signal disclosure")
        if "signal_offer = None" in main:
            raise ValueError("main has changed; manual signal merge required")
        anchor = '    return render(request, "core/financial_brand_page.html", {'
        if main.count(anchor) != 1:
            raise ValueError("render anchor drift")
        insertion = (
            "    # Read-only signal offer disclosure does not activate checkout.\n"
            "    signal_offer = None\n"
            "    if page_type == \"signals\":\n"
            "        from .signal_commercial_catalog import offer\n"
            "        signal_offer = offer(slug, locale)\n"
        )
        result = main.replace(anchor, insertion + anchor, 1)
        needle = '        "page_notice": notice, "copy": copy, "shop_url": shop_url,'
        if result.count(needle) != 1:
            raise ValueError("context anchor drift")
        result = result.replace(needle, needle + '\n        "signal_offer": signal_offer,', 1)
        require(result, (
            'request.get_host().split(":", 1)[0]',
            "signal_offer = offer(slug, locale)",
            '"destination_url": destination_url',
            '"free_destination_url": free_destination_url',
        ), "integrated signal and host")
        return result

    if path == "core/mojplaywin_product_detail.py":
        require(main, ("verified_guest_checkout_url(product.pk)",
                       "from .mojplaywin_checkout_route import verified_guest_checkout_url"),
                "main verified guest checkout")
        require(canonical, ('reverse("mpw_commerce:book"',), "canonical legacy checkout")
        # Main protects reverse->resolve handler parity; the earlier canonical
        # namespaced path check is weaker and must not downgrade it.
        return main

    if path == "core/templates/core/financial_brand_page.html":
        require(main, ("{{ destination_url }}", "{{ free_destination_url }}",
                       "button-free", "{% if page_type == \"signals\""),
                "main educational/free CTAs")
        start, end = "{% if signal_offer %}\n", "{% endif %}\n<footer"
        if canonical.count(start) != 1 or canonical.count(end) != 1:
            raise ValueError("canonical signal disclosure structure changed")
        panel = canonical[canonical.index(start):canonical.index(end) + len("{% endif %}\n")]
        if ("data-signal-subscription=\"not-released\"" not in panel
                or "No live subscription, checkout or guaranteed return" not in panel):
            raise ValueError("signal non-sale disclosure absent")
        footer = '<footer class="foot">'
        if main.count(footer) != 1 or "signal_offer" in main:
            raise ValueError("main signal disclosure drift")
        result = main.replace(footer, panel + footer, 1)
        return result

    if path == "core/tests/test_mpw_store_real_template_render.py":
        require(main, (b'href="/store/product/72/"'.decode(),
                       'self.assertNotIn(b\'href="/store/product/72/checkout/"\''),
                "main catalog guard")
        require(canonical, ("Never send funds to an address found outside your verified order invoice.",
                            "test_"), "canonical catalog assertion")
        # Main is authoritative for exact URL anchor checks; canonical tests
        # remain independently available in nonconflicting suites.
        return main

    if path == "services/mpw_trx_guest_commerce.py":
        require(main, (
            "def _new_trx_merchant_canary_is_true(config) -> bool:",
            "if not _new_trx_merchant_canary_is_true(settings):",
            "raise Http404(\"New TRX invoices unavailable\")",
        ), "main merchant payment hold")
        require(canonical, (
            'r"/commerce/trx-easy/invoice/[1-9][0-9]{0,18}/"',
            "getattr(response, \"status_code\", None) not in (302, 303)",
            "_record_funnel_event_best_effort",
        ), "canonical strict invoice analytics")
        start_marker = '                response = _dispatch(request, view, args, kwargs, create=make_claim)\n'
        end_marker = '                return response\n            wrapped.__name__ = view_name'
        if main.count(start_marker) != 1 or main.count(end_marker) != 1:
            raise ValueError("main order adapter drift")
        # Retrieve only canonical post-dispatch analytics, keeping main canary
        # check before _dispatch so a blocked checkout never provisions guest.
        if canonical.count(start_marker) != 1 or canonical.count(end_marker) != 1:
            raise ValueError("canonical invoice adapter drift")
        part = canonical.split(start_marker, 1)[1].split(end_marker, 1)[0]
        if ("return response" not in part or
                "r\"/commerce/trx-easy/invoice/[1-9][0-9]{0,18}/\"" not in part):
            raise ValueError("invoice proof no longer fail closed")
        before, after = main.split(start_marker, 1)
        _, suffix = after.split(end_marker, 1)
        result = (before + start_marker + part + end_marker + suffix)
        require(result, (
            "def _new_trx_merchant_canary_is_true(config) -> bool:",
            "raise Http404(\"New TRX invoices unavailable\")",
            'r"/commerce/trx-easy/invoice/[1-9][0-9]{0,18}/"',
        ), "integrated merchant and event safeguards")
        return result

    if path == "templates/moj-prop-v4/index.html":
        require(canonical, (
            "MOJ-PROP-01",
            'href="/moj-prop-interest/form/"',
            'href="/moj-prop-interest/form/?lang=fa"',
            "Other service requests — not Plan 1",
        ), "canonical prelaunch Plan1 CTA")
        require(main, ("MOJ-PROP-01",), "main existing Plan1")
        if 'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"' in canonical:
            raise ValueError("misrouted blueprint CTA reappeared")
        return canonical

    if path == "templates/moj-prop/contact/index.html":
        require(canonical, (
            'href="/moj-prop-interest/form/"',
            'href="/moj-prop-interest/form/?lang=fa"',
            "MOJ-PROP-01",
        ), "canonical bilingual contact")
        require(main, ("Moj Prop",), "existing public contact")
        return canonical

    raise AssertionError("unreachable")


def _command(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], check=False, capture_output=True,
                          timeout=45)


def _git_source(sha: str, path: str) -> str:
    result = _command("show", f"{sha}:{path}")
    if result.returncode != 0 or len(result.stdout) > MAX_BYTES:
        raise ValueError("reviewed input blob absent")
    return result.stdout.decode("utf-8", "strict")


def _unmerged_paths() -> tuple[str, ...]:
    result = _command("diff", "--name-only", "--diff-filter=U", "-z")
    if result.returncode != 0:
        raise ValueError("cannot inspect merge index")
    return tuple(sorted(p.decode("utf-8", "strict")
                        for p in result.stdout.split(b"\0") if p))


def main(argv: list[str]) -> int:
    if len(argv) != 3 or any(len(item) != 40 or
                             any(ch not in "0123456789abcdef" for ch in item)
                             for item in argv[1:]):
        raise SystemExit("usage: python resolver.py <pinned-main-commit> <pinned-canonical-commit>")
    main_sha, canonical_sha = argv[1:]
    conflicted = _unmerged_paths()
    if conflicted != tuple(sorted(CONFLICT_PATHS)):
        print("MOJPROP_C136_EXACT_CONFLICT_INVENTORY_MATCH=false")
        print("MOJPROP_C136_RELEASE_AUTHORIZED=false")
        return 3
    print("MOJPROP_C136_EXACT_CONFLICT_INVENTORY_MATCH=true")
    # Resolve all contents in memory first; a failed guard never partially
    # rewrites the worktree.
    answers = {path: resolve_source(
        path, _git_source(main_sha, path), _git_source(canonical_sha, path)
    ) for path in CONFLICT_PATHS}
    for path, content in answers.items():
        file = Path.cwd() / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("unexpected merge worktree path")
        file.write_text(content, encoding="utf-8")
    result = _command("add", "--", *CONFLICT_PATHS)
    if result.returncode != 0 or _unmerged_paths():
        raise ValueError("conflicts remain or source add failed")
    print("MOJPROP_C136_EXACT_EIGHT_SOURCE_CONFLICTS_RESOLVED=true")
    print("MOJPROP_C136_MAIN_MERCHANT_CANARY_PRESERVED=true")
    print("MOJPROP_C136_CANONICAL_STRICT_INVOICE_EVENT_PRESERVED=true")
    print("MOJPROP_C136_CANONICAL_OPTIN_ROUTE_PRESERVED=true")
    print("MOJPROP_C136_DEPLOYMENT_OR_PAID_SALE=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

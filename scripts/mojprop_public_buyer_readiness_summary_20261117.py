"""Strict, privacy-safe readiness outcome from GET HTML and transport evidence.

Only synthetic/fixed-key sanitized status data may be read. In particular,
valid HTML alone does not establish a live 200/0/zero-redirect endpoint.
Evidence collection can succeed while customer readiness is BLOCKED.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

KEYS = (
    "PUBLIC_MOJPROP_INTAKE_HTML_CONTRACT",
    "PUBLIC_MOJPROP_STATUS_HTML_CONTRACT",
    "PUBLIC_MOJPROP_NOJS_BACKEND_GATE",
    "PUBLIC_MOJPROP_NOJS_READONLY",
    "PUBLIC_MOJPROP_PAID_CHECKOUT_VERIFIED",
)
_ALLOWED = {
    KEYS[0]: frozenset(("PASS", "FAIL")),
    KEYS[1]: frozenset(("PASS", "FAIL")),
    KEYS[2]: frozenset(("PASS", "DEGRADED")),
    KEYS[3]: frozenset(("true",)),
    KEYS[4]: frozenset(("false",)),
}
TRANSPORT_KEYS = (
    "GET_ONLY_mojprop_intake_html_HTTP",
    "GET_ONLY_mojprop_intake_html_CURL_EXIT",
    "GET_ONLY_mojprop_intake_html_REDIRECTS",
    "GET_ONLY_mojprop_status_html_HTTP",
    "GET_ONLY_mojprop_status_html_CURL_EXIT",
    "GET_ONLY_mojprop_status_html_REDIRECTS",
)
_MAX_BYTES = 2048
_MAX_TRANSPORT_BYTES = 1024


def _strict_fixed_keys(source: str, keys: tuple[str, ...], allowed, max_bytes: int):
    if len(source.encode("utf-8")) > max_bytes:
        return None
    values: dict[str, str] = {}
    for line in source.splitlines():
        if "=" not in line:
            return None
        name, value = line.split("=", 1)
        if name not in keys or name in values or not allowed(name, value):
            return None
        values[name] = value
    return values if set(values) == set(keys) else None


def parse_contract_evidence(source: str) -> dict[str, str] | None:
    """Accept exactly five known non-secret contract decisions."""
    values = _strict_fixed_keys(
        source, KEYS, lambda name, value: value in _ALLOWED[name], _MAX_BYTES
    )
    if values is None:
        return None
    both = values[KEYS[0]] == "PASS" and values[KEYS[1]] == "PASS"
    if (values[KEYS[2]] == "PASS") != both:
        return None
    return values


def parse_transport_evidence(source: str) -> dict[str, str] | None:
    """Accept only numeric HTTP/transport/redirect outcomes for both endpoints.

    An HTTP 404/500 or curl error is retained as legitimate evidence but
    NEVER qualifies as a ready GET. Unknown/invalid evidence fails closed.
    """
    def allowed(name, value):
        if name.endswith("_HTTP"):
            return bool(re.fullmatch(r"(?:000|[1-5][0-9]{2})", value))
        if name.endswith("_CURL_EXIT"):
            return value == "unknown" or bool(re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", value))
        if name.endswith("_REDIRECTS"):
            return value == "unknown" or bool(re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", value))
        return False
    return _strict_fixed_keys(source, TRANSPORT_KEYS, allowed, _MAX_TRANSPORT_BYTES)


def _route_transport_pass(values: dict[str, str] | None, route: str) -> bool:
    if values is None:
        return False
    stem = "GET_ONLY_mojprop_" + route + "_html_"
    return (values[stem + "HTTP"] == "200"
            and values[stem + "CURL_EXIT"] == "0"
            and values[stem + "REDIRECTS"] == "0")


def summary(evidence: dict[str, str] | None,
            transport: dict[str, str] | None = None) -> tuple[str, str]:
    """Always require HTML + HTTP200 + exit0 + zero redirects for BOTH forms."""
    html_pass = bool(evidence and evidence[KEYS[2]] == "PASS")
    intake_live = _route_transport_pass(transport, "intake")
    status_live = _route_transport_pass(transport, "status")
    all_get = html_pass and intake_live and status_live
    readiness = "GET_HTML_ONLY_PASS_NOT_COMMERCIAL_READY" if all_get else "BLOCKED"
    intake = evidence[KEYS[0]] if evidence else "UNVERIFIED"
    private_status = evidence[KEYS[1]] if evidence else "UNVERIFIED"

    def route_state(route: str):
        if transport is None:
            return "UNVERIFIED"
        stem = "GET_ONLY_mojprop_" + route + "_html_"
        return ("HTTP " + transport[stem + "HTTP"]
                + " / curl exit " + transport[stem + "CURL_EXIT"]
                + " / redirects " + transport[stem + "REDIRECTS"])

    details = (
        "### MOJ PROP — live customer readiness: " + readiness,
        "",
        "| Read-only GET gate | Result |",
        "|---|---|",
        "| Native consent / intake HTML | " + intake + " |",
        "| Intake response status and redirect proof | " + route_state("intake") + " |",
        "| Private receipt-status POST-form HTML | " + private_status + " |",
        "| Private status response and redirect proof | " + route_state("status") + " |",
        "| Customer POST persisted | NOT TESTED |",
        "| TRON invoice / payment / settlement | NOT VERIFIED |",
        "| Independent full backup + restore / deployment authorization | NOT VERIFIED |",
        "",
        "**No paid launch permission is conferred by a successful GET or evidence job.**",
        "A redirect, non-200 status, curl error or missing proof blocks GET readiness.",
        "The evidence collector remains read-only; never enter customer data or wallet secrets.",
        "",
    )
    return readiness, "\n".join(details)


def _read_sanitized(path: Path, *, max_bytes: int) -> str | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise SystemExit(
            "usage: summary.py SANITIZED_HTML_CONTRACTS SANITIZED_HTTP_TRANSPORT GITHUB_STEP_SUMMARY"
        )
    c = _read_sanitized(Path(argv[1]), max_bytes=_MAX_BYTES)
    t = _read_sanitized(Path(argv[2]), max_bytes=_MAX_TRANSPORT_BYTES)
    evidence = parse_contract_evidence(c) if c is not None else None
    transport = parse_transport_evidence(t) if t is not None else None
    readiness, markdown = summary(evidence, transport)
    target = Path(argv[3])
    if target.is_symlink():
        raise SystemExit("GitHub summary path must not be a symlink")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("\n" + markdown)
    print("MOJPROP_LIVE_CUSTOMER_READINESS=" + readiness)
    print("MOJPROP_LIVE_EVIDENCE_IS_READ_ONLY=true")
    print("MOJPROP_LIVE_PAID_LAUNCH_AUTHORIZED=false")
    return 0  # A completed evidence job must never authorize commercial release.


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

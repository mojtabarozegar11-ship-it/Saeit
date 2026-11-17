"""Privacy-preserving buyer-path readiness summary from read-only GET evidence.

Input is the already-sanitized C123 classifier stdout, not an HTTP response
body. Never accepts CSRF values, receipt tokens, identity, or arbitrary HTML as
output. A green evidence-collection job is NOT a launch/release approval.
"""
from __future__ import annotations

from pathlib import Path
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
_MAX_BYTES = 2048


def parse_contract_evidence(source: str) -> dict[str, str] | None:
    """Accept exactly five known non-secret decisions; reject ambiguous input."""
    if len(source.encode("utf-8")) > _MAX_BYTES:
        return None
    values = {}
    for line in source.splitlines():
        if "=" not in line:
            return None
        name, value = line.split("=", 1)
        if name not in _ALLOWED or value not in _ALLOWED[name] or name in values:
            return None
        values[name] = value
    if set(values) != set(KEYS):
        return None
    both = values[KEYS[0]] == "PASS" and values[KEYS[1]] == "PASS"
    if (values[KEYS[2]] == "PASS") != both:
        return None
    return values


def summary(evidence: dict[str, str] | None) -> tuple[str, str]:
    both = bool(evidence and evidence[KEYS[2]] == "PASS")
    status = "GET_HTML_ONLY_PASS_NOT_COMMERCIAL_READY" if both else "BLOCKED"
    intake = evidence[KEYS[0]] if evidence else "UNVERIFIED"
    private_status = evidence[KEYS[1]] if evidence else "UNVERIFIED"
    details = (
        "### MOJ PROP — live customer readiness: " + status,
        "",
        "| Read-only GET gate | Result |",
        "|---|---|",
        "| Native consent / intake HTML | " + intake + " |",
        "| Private receipt-status POST-form HTML | " + private_status + " |",
        "| Customer POST persisted | NOT TESTED |",
        "| TRON invoice / payment / settlement | NOT VERIFIED |",
        "| Independent full backup + restore / deployment authorization | NOT VERIFIED |",
        "",
        "**No paid launch permission is conferred by a successful GET or evidence job.**",
        "The evidence collector remains read-only; never enter customer data or wallet secrets.",
        "",
    )
    return status, "\n".join(details)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: summary.py SANITIZED_CLASSIFIER_OUTPUT GITHUB_STEP_SUMMARY")
    try:
        source = Path(argv[1])
        # Deny symlinks, directories and oversized unexpected classifier logs.
        if source.is_symlink() or not source.is_file() or source.stat().st_size > _MAX_BYTES:
            evidence = None
        else:
            evidence = parse_contract_evidence(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        evidence = None
    status, markdown = summary(evidence)
    target = Path(argv[2])
    # The summary destination is provided by GitHub Actions; avoid writing
    # accidental symlink targets if a runner misconfigures the environment.
    if target.is_symlink():
        raise SystemExit("GitHub summary path must not be a symlink")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("\n" + markdown)
    print("MOJPROP_LIVE_CUSTOMER_READINESS=" + status)
    print("MOJPROP_LIVE_EVIDENCE_IS_READ_ONLY=true")
    print("MOJPROP_LIVE_PAID_LAUNCH_AUTHORIZED=false")
    return 0  # NEVER claim payment or suppress the read-only evidence run.


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

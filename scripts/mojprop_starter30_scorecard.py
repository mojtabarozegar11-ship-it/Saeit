"""Generate an actual offline printable educational deliverable for Starter30.

Never send this file to an arbitrary address or treat it as a payment receipt.
The caller must independently verify buyer ownership and permitted delivery.
"""
from __future__ import annotations

from html import escape
import re

from scripts.mojprop_starter30 import assess_journal

_ID = re.compile(r"MPS30-[A-Z0-9]{8,24}\Z")


def _recommendations(breaches: list[dict]) -> list[str]:
    rules = {x["rule"] for x in breaches}
    result = []
    if "daily_loss" in rules:
        result.append("Reduce simulated exposure and write a stop condition before each session.")
    if "overall_peak_drawdown" in rules:
        result.append("Introduce a simulated peak-equity drawdown guard and review every loss sequence.")
    if "risk_plan_missing" in rules:
        result.append("Write a risk plan before each session and note the invalidation level.")
    if "reflection_missing" in rules:
        result.append("Document an end-of-session reflection, including process deviations.")
    if not result:
        result.append("Maintain the risk journal and review how rule adherence changes over time.")
    return result


def render_private_scorecard(rows: object, case_reference: str) -> str:
    """Render a print-ready feedback document without customer names or PII."""
    if type(case_reference) is not str or not _ID.fullmatch(case_reference):
        raise ValueError("case reference must be an opaque verified MPS30 identifier")
    result = assess_journal(rows)
    recommendations = _recommendations(result["rule_breaches"])
    by_rule = ("; ".join(
        "Session " + str(item["session"]) + ": " + item["rule"].replace("_", " ")
        for item in result["rule_breaches"]
    ) or "None in the supplied self-reported journal")
    bullets = "".join("<li>" + escape(item) + "</li>" for item in recommendations)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Moj Prop Starter 30 — Private educational scorecard</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:1rem;color:#151515}}
h1{{font-size:2rem}}.data{{border:1px solid #999;padding:15px;border-radius:7px}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>Moj Prop Starter 30 — Educational scorecard</h1>
<p>Case reference: <strong>{escape(case_reference)}</strong></p>
<div class="data"><p>Result: <strong>{escape(result["status"])}</strong></p>
<p>Sessions documented: {result["documented_sessions"]} of {result["sessions_recorded"]} received;
completion requires 10 consecutive sessions.</p>
<p>Closing simulated equity: {escape(result["closing_simulated_equity_usd"])} reference USD
(not owned, funded or withdrawable).</p>
<p>Risk-rule observations: {escape(by_rule)}</p></div>
<h2>Individual learning recommendations</h2><ul>{bullets}</ul>
<p><strong>Limitations:</strong> Scores assess self-reported simulation notes only. This report does
not verify brokerage trades, authorise a funded account, certify profitability,
offer investment advice or indicate any payment was received.</p>
<p>Operator identity: mojtaba.bot.ai · Product: MOJPROP-STARTER30</p>
</body></html>"""


__all__ = ["render_private_scorecard"]

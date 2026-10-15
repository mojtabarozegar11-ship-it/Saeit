#!/usr/bin/env python3
"""Printable local report of the independent farm land/water LP audit."""
import argparse
from html import escape
import json
import os
from pathlib import Path
import tempfile

HEAD="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Farm Water & Land Margin Audit</title><style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#1e3428;background:#f4f7f3}
*{box-sizing:border-box}body{margin:0}
header{background:#15372b;border-bottom:5px solid #bb9e56;color:white;padding:38px max(24px,calc((100vw - 1070px)/2))}
header h1{font-size:clamp(28px,5vw,49px);margin:6px 0}.tag{letter-spacing:.16em;color:#d6c394;font-size:11px}
main{max-width:1130px;padding:22px;margin:auto}.warning{padding:18px;margin:16px 0;background:#fff1dd;border-left:5px solid #b58d44;border-radius:7px}
.card{background:white;border:1px solid #d9e6dc;border-radius:14px;padding:22px;margin:20px 0}
.grid{display:flex;gap:12px;flex-wrap:wrap}.stat{background:#ecf4ed;border-radius:9px;padding:12px;flex:1;min-width:140px}
.stat small{display:block;color:#496b56}.stat strong{font-size:21px}
table{border-collapse:collapse;width:100%;min-width:680px;font-size:12px}th,td{padding:12px 7px;text-align:left;border-bottom:1px solid #e3eae3}th{font-size:11px;color:#536f5a}
.scrolling{overflow-x:auto}li{margin:7px 0;line-height:1.5;font-size:12px}
footer{padding:24px;text-align:center;font-size:11px;color:#607666}
@media print{@page{size:A4;margin:10mm}header{background:white;color:#111;border-bottom:2px solid #444}
body{background:white}.card{break-inside:avoid;box-shadow:none}.scrolling{overflow:visible}table{min-width:0;font-size:9px}}
</style></head><body><header><div class="tag">ASTRA 2.0 / PRIVATE R&D AUDIT</div>
<h1>Farm Water & Land Margin Audit</h1><p>Transparent crop-mix optimization under declared land and water limits</p></header>
<main><div class="warning"><strong>Hypothetical arithmetic, NOT an irrigation recommendation.</strong>
Data are operator-supplied; no crop water model, permits, rotations, soil effects, or external buyer prices are independently validated.</div>
"""


def render(doc):
    if doc.get("product") != "farm_water_land_margin_audit_private_reference_mvp":
        raise ValueError("unrecognized audit report")
    if doc.get("sale_ready") is not False or doc.get("store_publication_authorized") is not False:
        raise ValueError("commercial release metadata must be explicitly false")
    parts=[HEAD]
    x=lambda v:escape(str(v),quote=True)
    parts.append('<div class="card"><h2>Inputs and scenario method</h2><p><b>Currency:</b> '+
                 x(doc["currency"]) + ' · <b>Water:</b> m³ · <b>Area:</b> hectares</p>'+
                 '<p>Assumed drought water fraction: '+x(doc["drought_water_fraction"])+
                 '. Gross margin excludes fixed capital/overhead and other constraints.</p></div>')
    for key,title in (("baseline","Base available water"),("water_scarcity","Reduced available water")):
        d=doc[key]
        parts.append('<section class="card"><h2>'+title+'</h2><div class="grid">')
        for name,field in (("Total gross margin","total_gross_margin"),
                           ("Land used (ha)","allocated_land_hectares"),
                           ("Water used (m³)","water_m3_used")):
            parts.append('<div class="stat"><small>'+name+'</small><strong>'+
                         x(d[field])+'</strong></div>')
        parts.append('</div><div class="scrolling"><table><thead><tr>'+
                     '<th>Crop</th><th>Allocated hectares</th><th>Gross margin / ha</th>'+
                     '<th>Margin contribution</th><th>Water used (m³)</th>'+
                     '<th>Evidence verified?</th></tr></thead><tbody>')
        for row in d["allocation"]:
            parts.append("<tr>"+''.join("<td>"+x(val)+"</td>" for val in (
                row["crop"],row["hectares"],row["gross_margin_per_hectare"],
                row["gross_margin_contribution"],row["water_m3_used"],"No"))+"</tr>")
        parts.append("</tbody></table></div><p>Unused land: "+x(d["unused_land_hectares"])+
                     " ha · Unused water: "+x(d["unused_water_m3"])+
                     " m³ · Candidate vertices considered: "+x(d["vertices_tested"])+
                     "</p></section>")
    frontier = doc.get("water_sensitivity_frontier")
    if not isinstance(frontier, list) or len(frontier) != 5:
        raise ValueError("missing five-point water sensitivity frontier")
    parts.append('<section class="card"><h2>Water allowance sensitivity</h2>'
                 '<p>All points re-optimize the same user-supplied linear model. '
                 'Interval values are <strong>average gross-margin gains per '
                 'extra m³ of allowed water</strong>; they are NOT a market '
                 'water price, a continuously differentiable dual value, '
                 'real-world profitability, or permission to pump more water.'
                 '</p><div class="scrolling"><table><thead><tr>'
                 '<th>Water budget (fraction of baseline)</th><th>Budget (m³)</th>'
                 '<th>Water used (m³)</th><th>Optimal gross margin</th>'
                 '<th>Gross margin gain since prior point</th>'
                 '<th>Average gain per added m³ (currency/m³)</th>'
                 '</tr></thead><tbody>')
    for row in frontier:
        if row.get("farm_result_verified") is not False or (
                row.get("market_water_price_or_dual_shadow_price") is not None):
            raise ValueError("frontier metadata cannot claim verification")
        parts.append("<tr>" + "".join("<td>" + x(value) + "</td>" for value in (
            str(row["water_budget_fraction"]),
            row["water_budget_m3"],
            row["water_used_m3"],
            row["optimal_gross_margin"],
            row["gross_margin_gain_in_interval"]
            if row["gross_margin_gain_in_interval"] is not None else "—",
            row["average_incremental_gross_margin_per_m3"]
            if row["average_incremental_gross_margin_per_m3"] is not None else "—",
        )) + "</tr>")
    parts.append("</tbody></table></div></section>")
    parts.append('<div class="card"><h2>Risks and missing real-world checks</h2><ul>')
    for warning in doc["warnings"]:
        parts.append("<li>"+x(warning)+"</li>")
    parts.append("</ul><p>Source/price verification: none. Market qualification: none. "+
                 "Retail release approval: false.</p><small>Input SHA-256: "+x(doc["input_sha256"])+
                 "</small></div>")
    return "".join(parts)+"</main><footer>Not a certified farm management recommendation; specialist review required.</footer></body></html>"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True)
    p.add_argument("--html",required=True)
    args=p.parse_args()
    src=Path(args.report).expanduser()
    dest=Path(args.html).expanduser()
    if src.is_symlink() or not src.is_file() or src.stat().st_size>250000:
        raise ValueError("invalid source")
    if dest.is_symlink() or dest.exists() or not dest.resolve().parent.is_dir():
        raise ValueError("unsafe destination")
    output=render(json.loads(src.read_text(encoding="utf-8")))
    fd,name=tempfile.mkstemp(dir=str(dest.resolve().parent),prefix=".water-audit-")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(output);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600)
        os.link(name,dest)
    finally:
        if os.path.exists(name):os.unlink(name)
    print("FARM_WATER_LAND_HTML=PRIVATE_AUDIT")


if __name__=="__main__":
    main()

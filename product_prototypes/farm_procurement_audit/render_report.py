#!/usr/bin/env python3
"""Create a local print-ready procurement comparison from audited JSON."""
import argparse
from html import escape
import json
import os
from pathlib import Path
import tempfile

HEAD="""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Farm Procurement Audit</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#192d24;background:#f3f6f2}
*{box-sizing:border-box}body{margin:0}.top{background:#153a2d;color:#fff;padding:28px max(24px,calc((100vw - 1040px)/2));border-bottom:5px solid #c3a769}
main{max-width:1100px;margin:auto;padding:32px 24px}.eyebrow{font-size:11px;letter-spacing:.2em;color:#91af93;font-weight:800}
h1{font-size:clamp(28px,5vw,50px);margin:8px 0}.intro{color:#d5e2d8;max-width:740px;line-height:1.7}
.notice{background:#fff4e0;border-left:5px solid #b28543;padding:17px;margin:22px 0;border-radius:8px}
.metrics{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}.metric{background:white;border:1px solid #d7e3db;padding:19px;border-radius:12px;flex:1;min-width:160px}
.metric small{display:block;color:#67816d}.metric strong{font-size:20px}.card{background:white;border:1px solid #d7e3db;border-radius:14px;padding:24px;margin-top:20px}
table{border-collapse:collapse;width:100%;min-width:660px;font-size:13px}th,td{text-align:left;padding:12px 9px;border-bottom:1px solid #e2e9e0}
th{color:#4b6654;font-size:11px;text-transform:uppercase}.scroll{overflow-x:auto}
.eligible{color:#23744b;font-weight:800}.blocked{color:#9b422f;font-weight:800}
footer{padding:30px 24px;text-align:center;font-size:12px;color:#6c7c72}
@media print{@page{size:A4;margin:12mm}body{background:#fff}.top{background:#fff;color:#111}.intro,.eyebrow{color:#444}.card{break-inside:avoid;box-shadow:none}.scroll{overflow:visible}table{min-width:0;font-size:9px}}
</style></head><body><div class="top"><div class="eyebrow">ASTRA 2.0 · PRIVATE RESEARCH TOOL</div>
<h1>Farm Procurement Quote Audit</h1><p class="intro">Transparent landed-cost comparisons with delivery constraints, gross-to-net yield allowances and conservative stress tests.</p></div><main>
<div class="notice"><strong>Not a verified quote or purchase recommendation.</strong>
Every supplier and price must be checked with the actual provider. The application does not confirm taxes, quality, availability, supplier identity or buyer demand.</div>
"""


def report_html(doc):
    if not isinstance(doc,dict) or doc.get("product")!="farm_input_procurement_audit_private_reference_mvp":
        raise ValueError("only certified-schema private procurement calculation reports supported")
    if doc.get("commercial_release_allowed") is not False or doc.get("market_demand_verified") is not False:
        raise ValueError("unverified claims or commercial release flags refused")
    x=escape
    html=[HEAD,'<div class="metrics">',
          '<div class="metric"><small>Currency / input unit</small><strong>'+x(str(doc["currency"]))+' / '+x(str(doc["unit"]))+'</strong></div>',
          '<div class="metric"><small>Usable quantity requested</small><strong>'+x(str(doc["net_units_required"]))+'</strong></div>',
          '<div class="metric"><small>Delivery deadline</small><strong>'+x(str(doc["deadline_days"]))+' days</strong></div></div>']
    mode=doc.get("declared_spec_comparison_mode","legacy_spec_comparability_unassessed")
    if mode=="buyer_supplied_metadata_not_independently_authenticated":
        html.append('<div class="notice"><strong>Buyer-declared comparability gate:</strong> '
            'product specification '+x(str(doc.get("buyer_required_product_spec_ref")))+
            '; quote evaluation date '+x(str(doc.get("as_of_date_operator_supplied")))+
            '. Inconsistent, expired, future-dated or undocumented quotes are excluded '
            'from the arithmetic eligible shortlist. Supplier identities, quote documents '
            'and product equivalence have NOT been independently verified.</div>')
    else:
        html.append('<div class="notice"><strong>Legacy comparison mode:</strong> '
            'product specification equivalence and quote validity dates were NOT checked. '
            'Do not treat the arithmetic lowest offer as a comparable supplier recommendation.</div>')
    for key in ("base","adverse"):
        data=doc["scenarios"][key]
        html.append('<section class="card"><h2>'+x(key.title())+' scenario</h2>')
        winner=data["lowest_cost_eligible_supplier_under_inputs"]
        html.append("<p><strong>Lowest arithmetic eligible offer:</strong> "+x(winner if winner else "None eligible")+"</p>")
        gap=data.get("arithmetic_cost_gap_to_second_eligible_not_realized_savings")
        if gap is not None:
            html.append("<p><strong>Arithmetic gap to second eligible offer (NOT realized savings):</strong> "+
                        x(str(gap))+" "+x(str(doc["currency"]))+". "+
                        "Quote terms, quality, taxes and supplier identity remain unverified.</p>")
        html.append('<div class="scroll"><table><thead><tr><th>Supplier</th><th>Eligible?</th><th>Price basis</th><th>Whole packs</th><th>Gross units ordered</th><th>Excess usable units</th><th>Landed total</th><th>Effective cost/net unit</th><th>Limitations</th></tr></thead><tbody>')
        for offer in data["offers"]:
            eligible=offer["eligible_for_cost_comparison"]
            html.append("<tr><td>"+x(str(offer["supplier"]))+
                 "</td><td class='"+("eligible" if eligible else "blocked")+"'>"+("Yes" if eligible else "No")+
                 "</td><td>"+x(str(offer.get("quote_pricing_basis","per_base_unit")))+
                 "</td><td>"+x(str(offer.get("whole_packs_ordered") or "N/A"))+
                 "</td><td>"+x(str(offer.get("gross_order_units","N/A")))+
                 "</td><td>"+x(str(offer.get("surplus_usable_units","N/A")))+
                 "</td><td>"+x(str(offer.get("total_landed_cost","N/A")))+
                 "</td><td>"+x(str(offer.get("landed_cost_per_net_required_unit","N/A")))+
                 "</td><td>"+x(", ".join(offer["reasons"]) if offer["reasons"] else "None reported")+"</td></tr>")
        html.append("</tbody></table></div></section>")
    html.append('<section class="card"><h2>Limitations and verification</h2><ul>')
    for item in doc["warnings"]:
        html.append("<li>"+x(str(item))+"</li>")
    html.append("</ul><p><strong>Market validation:</strong> not verified. <strong>Product sale readiness:</strong> blocked.</p>")
    html.append("<p><small>Source data digest: "+x(str(doc["input_sha256"]))+"</small></p></section>")
    html.append("</main><footer>ASTRA V2 private reference prototype · For independent review only</footer></body></html>")
    return "".join(html)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",required=True)
    parser.add_argument("--html",required=True)
    args=parser.parse_args(argv)
    src=Path(args.report).expanduser()
    dst=Path(args.html).expanduser()
    if src.is_symlink() or not src.is_file() or src.stat().st_size>500000 or dst.is_symlink() or dst.exists():
        raise ValueError("unsafe report or existing output")
    source=src.resolve(strict=True)
    out=dst.resolve()
    if out==source or not out.parent.is_dir():
        raise ValueError("invalid output path")
    text=report_html(json.loads(source.read_text(encoding="utf-8")))
    fd,staged=tempfile.mkstemp(dir=str(out.parent),prefix=".procurement-audit-")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(text)
            f.flush();os.fsync(f.fileno())
        os.chmod(staged,0o600)
        os.link(staged,out)
    finally:
        if os.path.exists(staged):os.unlink(staged)
    print("FARM_PROCUREMENT_HTML_REPORT=PRIVATE_REFERENCE_ONLY")


if __name__=="__main__":
    main()

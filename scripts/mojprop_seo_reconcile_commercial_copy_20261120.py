"""Exact five-page SEO publication candidate reconciliation, NO live writes.

Requires the original pinned live bytes. Retains legacy builder unchanged;
only reviewed visible English sales-navigation text changes are added.
No activation, DB access, payment processing, release gate or deployment.
"""
from scripts.mojprop_seo_exact_live_candidate_20261120 import build_candidate, sha

PATCHES = {
    "index.html": (
        ("The current commercial route supports manual requests, research briefs and education. No profit promise, live account or hidden activation is presented as available.",
         "Research services use manual requests. Starter 30 is a separate simulated trading challenge at 30 TRX; check its current eligibility, terms and secure checkout availability. No real funded broker account or guaranteed profit."),
        ("paid challenges, live accounts, KYC, automatic payment and profit guarantees are not active. Current route: request draft → human/legal review → written offer → approved payment path → delivery and receipt.",
         "Research services follow the manual review and written-offer route. Starter 30 has a separate simulated challenge and secure checkout; pay only against a unique server-issued invoice if checkout confirms availability. No customer capital custody or guaranteed profit."),
        ("Does Moj Prop currently sell a live account or paid challenge?",
         "Does Moj Prop offer a real funded account or a simulated challenge?"),
        ("No. Live accounts, paid challenges and automatic payment remain locked until legal identity, contracts, KYC and risk infrastructure are approved.",
         "No real funded brokerage account is offered here. Review the separate Starter 30 simulated challenge and current checkout conditions before deciding."),
        ("No public wallet address is displayed. If a lawful route is approved, the method and amount are disclosed only in a written invoice.",
         "No public receiving address is displayed here. For Starter 30, use the dedicated secure checkout and send funds only after a unique invoice is issued. Research services use a separate written-offer process."),
        ('<span>Automatic payment</span><b>LOCKED</b>',
         '<span>Starter 30 checkout</span><b>CHECK STATUS</b>'),
    ),
    "catalog/index.html": (
        ("Every engagement starts with a request draft and a written offer.",
         "These four research services start with a request draft and written offer. The separate Starter 30 simulated challenge costs 30 TRX; check its current terms and checkout availability."),
        ('<section class="process">', '<section class="hero"><div class="eyebrow">SEPARATE SIMULATED CHALLENGE</div><h2>Starter 30 — 30 TRX</h2><p>60-day simulated challenge with a virtual $1,000 balance. Review eligibility, risk rules and payout terms. No real funded brokerage account, customer capital custody or guaranteed profit. Pay only against a unique server-issued invoice when checkout confirms availability.</p><a class="cta" href="/moj-prop/starter-30-trx/">View Starter 30 details</a> · <a href="/mojprop-starter30-checkout/">Check secure checkout</a></section><section class="process">'),
    ),
    "payment/index.html": (
        ("automatic checkout, KYC, paid challenges and live accounts are not active. No public TRX wallet address is displayed. Requests are reviewed as drafts first.",
         'Research-service requests are reviewed as drafts first. Starter 30 uses a separate simulated challenge checkout: <a href="/moj-prop/starter-30-trx/">review product terms</a> and <a href="/mojprop-starter30-checkout/">check secure checkout availability</a>. Send 30 TRX only against a unique server-issued invoice. No public wallet address is displayed here; no real funded brokerage account or guaranteed profit.'),
    ),
}

def reconcile_candidate(path, original):
    initial, receipt = build_candidate(path, original)
    text = initial.decode("utf-8", errors="strict")
    head, body = text.split("</head>", 1)
    changed = body
    for old, new in PATCHES.get(path, ()):
        if changed.count(old) != 1:
            raise ValueError("unrecognized reviewed text anchor")
        changed = changed.replace(old, new, 1)
    # Existing non-structured scripts, form and styling must be byte-identical;
    # only the listed text anchors are eligible for changes.
    import re
    for pattern in (r"<script\\b[^>]*>.*?</script>", r"<form\\b[^>]*>.*?</form>", r"<style\\b[^>]*>.*?</style>"):
        if re.findall(pattern, body, re.S|re.I) != re.findall(pattern, changed, re.S|re.I):
            raise ValueError("functional markup changed")
    result = (head + "</head>" + changed).encode("utf-8")
    receipt.update({"first_candidate_sha256": sha(initial), "after_sha256": sha(result),
                    "copy_patch_count": len(PATCHES.get(path, ())),
                    "body_after_sha256": sha(changed.encode("utf-8")),
                    "deployment_authorized": False})
    return result, receipt

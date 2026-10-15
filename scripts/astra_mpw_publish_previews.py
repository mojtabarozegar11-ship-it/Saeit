#!/usr/bin/env python3
"""Publish honest Astra product PREVIEW pages without enabling unsafe checkout.

Four original source bundles stay PRIVATE. Public pages and an index are
informational and explicitly labelled NOT FOR SALE. Does not change the
factory-managed Product.active flag or bypass its release gate.
"""
import argparse
from html import escape
import os
from pathlib import Path
import re
import tempfile
from astra_mpw_four_draft_import import verify_store_bundle

SLUGS = {
    "ASTRA-CIRCUIT-01": "circuit-courier",
    "ASTRA-PROCURE-01": "farm-procurement-audit",
    "ASTRA-WATER-01": "farm-water-land-margin-audit",
    "ASTRA-ORCHARD-01": "orchard-decision-audit",
}
BASE_URL = "https://mojplaywin.com/factory-previews/"
BEGIN = "<!-- ASTRA_FOUR_OWNER_PREVIEW_START -->"
END = "<!-- ASTRA_FOUR_OWNER_PREVIEW_END -->"


def page(title, content, canonical, description):
    title = escape(title)
    canonical = escape(canonical, quote=True)
    description = escape(description, quote=True)
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow">
<title>""" + title + """ | MojPlayWin</title>
<meta name="description" content="""" + description + """">
<link rel="canonical" href="""" + canonical + """">
<style>*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:#0b121c;color:#f0f4fa;font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:#fbd88e}a:focus-visible{outline:3px solid #ffdb7e;outline-offset:4px}
header,main,footer{max-width:1030px;margin:auto;padding:24px}
header,footer{border-bottom:1px solid #344151}
footer{border-top:1px solid #344151;border-bottom:0;margin-top:50px}
.eyebrow{letter-spacing:.12em;text-transform:uppercase;color:#efc77c;font-weight:700;font-size:.82rem}
h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.15;margin:15px 0}
h2{font-size:1.35rem}p{max-width:75ch;color:#cbd7e5}
.card{background:#162331;border:1px solid #334455;border-radius:16px;padding:22px;margin:18px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.grid .card{margin:0}.note{color:#f8e9c9}.pill{display:inline-block;background:#2b3745;border-radius:40px;
padding:5px 14px;font-size:.85rem;font-weight:700}
.price{font-size:1.3rem;color:#fce4ac}small{color:#c6d2de}
</style></head><body>
<header><nav aria-label="Breadcrumb"><a href="https://mojplaywin.com/">MojPlayWin</a>
 / <a href="/store/">Store</a> / <a href="/factory-previews/">Astra previews</a></nav></header>
<main>""" + content + """</main>
<footer>© 2026 MojPlayWin · Owner-submitted Astra preview information. 
No payment is requested on these pages.</footer></body></html>\n""")


def render(rows):
    by_sku = {x["sku"]: x for x in rows}
    if set(by_sku) != set(SLUGS):
        raise ValueError("require precisely four known SKU packages")
    pages = {}
    links = []
    cards = []
    for sku, slug in SLUGS.items():
        data = by_sku[sku]
        title, description = escape(data["title"]), escape(data["summary"])
        limits = escape(data["limits"])
        amount = escape(data["sale_usd"])
        link = "/factory-previews/" + slug + "/"
        cards.append('<article class="card"><span class="pill">PUBLIC PREVIEW · NOT FOR SALE</span>'
                     '<h2>'+title+'</h2><p>'+description+'</p><p><a href="'+link+
                     '">Read the product preview →</a></p></article>')
        links.append('<article class="mpw-page-card"><small>ASTRA EARLY PREVIEW · NOT FOR SALE</small>'
                     '<h2>'+title+'</h2><p>'+description+'</p>'
                     '<p>Proposed launch price: $'+amount+' USD · checkout not open</p>'
                     '<a href="'+link+'">Explore preview →</a></article>')
        body = ('<span class="eyebrow">Astra Original Products / Preview</span><h1>'+title+
                '</h1><span class="pill">Not available for purchase</span>'
                '<p>'+description+'</p><section class="card"><h2>Who it is for</h2>'
                '<p>Customers exploring independently built specialist digital products.</p>'
                '<h2>Current technical status</h2><p>A private ZIP build passed internal '
                'technical regression and checksum verification. No public download or buyer '
                'entitlement has yet been released.</p></section>'
                '<section class="card"><h2>Proposed launch pricing</h2>'
                '<p class="price">$'+amount+' USD · proposed 90% introductory discount</p>'
                '<p>The price is provisional. It is <strong>not</strong> an available checkout '
                'offer. Do not send cryptocurrency to purchase this product.</p></section>'
                '<section class="card"><h2>Important limitations</h2><p>'+limits+
                '</p><p>Independent usability, third-party dependency licensing, final rights '
                'review, commercial suitability and payment-to-delivery verification remain '
                'in progress.</p></section><p><a href="/store/">Back to MojPlayWin store</a></p>')
        pages[slug+"/index.html"] = page(data["title"],body,BASE_URL+slug+"/",
                                            data["summary"])
    main = ('<span class="eyebrow">Astra product studio</span>'
            '<h1>Four original digital product previews</h1>'
            '<p>These are previews of software and game candidates under technical and '
            'commercial evaluation, <strong>not products currently offered for purchase</strong>. '
            'Downloads and crypto checkout are not available for these four candidates yet.</p>'
            '<section class="grid">'+''.join(cards)+'</section>')
    pages["index.html"] = page("Astra Product Previews",main,BASE_URL,
                                "Four independently built digital product previews")
    section = (BEGIN + '<section class="mpw-page-grid" id="astra-previews">'
               + ''.join(links)+'</section>' + END)
    return pages,section


def make_plan(catalog, packages, public_root, store_template):
    rows = verify_store_bundle(catalog,packages)
    pages, section = render(rows)
    root=Path(public_root)
    template=Path(store_template)
    if (not root.is_absolute() or root.is_symlink() or root.name!="mojplaywin.com"
            or not root.is_dir() or not template.is_file() or template.is_symlink()
            or template.name!="store.html" or not (root/"passenger_wsgi.py").is_file()
            or "Saeit-staging" not in (root/"passenger_wsgi.py").read_text()):
        raise ValueError("live MojPlayWin Django storefront not verified")
    source=template.read_text(encoding="utf-8")
    anchor='<section class="mpw-page-cta"><small>PAYMENTS</small>'
    if (BEGIN in source) != (END in source):
        raise ValueError("partial store marker; refusing modification")
    if BEGIN in source:
        first=source.index(BEGIN)
        last=source.index(END)+len(END)
        if source[first:last] != section:
            raise ValueError("existing Astra store preview differs; no replacement allowed")
        replacement=source
    else:
        if source.count(anchor)!=1:
            raise ValueError("unknown active storefront template layout")
        replacement=source.replace(anchor,section+anchor)
    parent=root/"factory-previews"
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise ValueError("unsafe factory preview directory")
    for rel,data in pages.items():
        path=parent/rel
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("unsafe preview target")
        if path.exists() and path.read_bytes()!=data.encode("utf-8"):
            raise ValueError("conflicting public page; no overwrite")
    return {"pages":pages,"parent":parent,"template":template,
            "old":source,"new":replacement}


def _create_new_file(path,payload):
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,"wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def publish(plan, backup_dir, *, apply=False):
    if not apply:
        return {"status":"DRY_RUN","pages":len(plan["pages"]),"template_change":
                plan["old"]!=plan["new"]}
    backups=Path(backup_dir)
    if backups.is_symlink() or not backups.is_dir():
        raise ValueError("private backup directory not verified")
    parent=plan["parent"]
    parent.mkdir(mode=0o755,exist_ok=True)
    for rel,page_data in plan["pages"].items():
        target=parent/rel
        target.parent.mkdir(mode=0o755,exist_ok=True)
        if not target.exists():
            _create_new_file(target,page_data.encode("utf-8"))
    if plan["old"]!=plan["new"]:
        import hashlib
        digest=hashlib.sha256(plan["old"].encode()).hexdigest()[:20]
        backup=backups/("mojplaywin-store-before-astra-"+digest+".html")
        if not backup.exists():
            _create_new_file(backup,plan["old"].encode("utf-8"))
            backup.chmod(0o600)
        elif backup.read_text(encoding="utf-8")!=plan["old"]:
            raise ValueError("conflicting existing private backup")
        handle,tmp=tempfile.mkstemp(prefix=".astra-mpw-",dir=str(plan["template"].parent))
        try:
            with os.fdopen(handle,"w",encoding="utf-8") as out:
                out.write(plan["new"])
                out.flush()
                os.fsync(out.fileno())
            os.chmod(tmp,plan["template"].stat().st_mode & 0o777)
            os.replace(tmp,plan["template"])
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return {"status":"PUBLIC_PREVIEWS_PUBLISHED",
            "pages":len(plan["pages"]),
            "template_change":plan["old"]!=plan["new"]}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog",required=True)
    ap.add_argument("--packages",required=True)
    ap.add_argument("--public-root",required=True)
    ap.add_argument("--store-template",required=True)
    ap.add_argument("--backups",required=True)
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args(argv)
    plan=make_plan(args.catalog,args.packages,args.public_root,args.store_template)
    result=publish(plan,args.backups,apply=args.apply)
    for k,v in sorted(result.items()):
        print("ASTRA_PREVIEW_"+k.upper()+"="+str(v))
    print("ASTRA_PREVIEW_FACTORY_DRAFT_ACTIVATIONS=0")
    print("ASTRA_PREVIEW_CHECKOUT_ENABLED=0")
    print("ASTRA_PREVIEW_PRIVATE_ZIPS_PUBLIC=0")


if __name__=="__main__":
    main()

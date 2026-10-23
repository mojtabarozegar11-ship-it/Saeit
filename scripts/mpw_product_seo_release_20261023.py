#!/usr/bin/env python3
"""Bounded MojPlayWin SEO metadata and Product JSON-LD release."""
from __future__ import annotations
import hashlib, json, os, re, stat, sys, tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path('/home/zomorod2/Saeit-staging')
VIEW = ROOT / 'core/brand_views.py'
TEMPLATE = ROOT / 'core/templates/brands/mojplaywin/product.html'
HOME = Path('/home/zomorod2')
EXPECTED = {
    72: ('The Science and Practice of Chess Improvement', '7.50'),
    225: ('Taniya and the Little Baker Worms', '4.00'),
    879: ('Atelier Interior — Client-Ready Website Kit', '6.80'),
}
CONTENT = {
    72: {
        'summary': 'Build stronger chess calculation and decision-making habits with an evidence-informed 84-day training guide. Includes critical-position review worksheets, human-first game review, and practice and progress tracking for players who want a structured chess improvement plan.',
        'seo_description': 'An 84-day chess improvement guide with calculation practice, critical-position worksheets, human-first game review and progress tracking.',
        'seo_keywords': ['chess improvement guide', '84-day chess training plan', 'chess calculation practice', 'chess decision making', 'critical position worksheet', 'chess progress tracking'],
        'ai_summary': 'Digital chess training guide with an 84-day curriculum, evidence-informed practice, decision-making and calculation work, critical-position review worksheets, human-first game review, and progress tracking.',
        'language': 'en',
    },
    225: {
        'summary': 'Read Taniya and the Little Baker Worms, an English rhythmic read-aloud picture book presented as a 40-page illustrated PDF. The digital book includes its front and back covers and is designed for shared story time and young readers.',
        'seo_description': 'Taniya and the Little Baker Worms is a 40-page illustrated PDF picture book with an English rhythmic read-aloud story and covers.',
        'seo_keywords': ['illustrated picture book PDF', 'read-aloud story for children', 'English rhythmic storybook', '40-page digital picture book', 'Taniya and the Little Baker Worms'],
        'ai_summary': 'A digital English-language picture book in PDF format, with 40 illustrated pages, a rhythmic read-aloud story, and front and back covers.',
        'language': 'en',
    },
    879: {
        'summary': 'Launch a polished interior-design studio website with the Atelier Interior client-ready kit. The downloadable ZIP includes responsive HTML, CSS and JavaScript, editable brand and contact details, five original SVG interior illustrations, setup instructions, and a non-exclusive one-site/client license. Demo photographs are not included.',
        'seo_description': 'A responsive interior design website template kit with editable branding, five SVG illustrations, source files, setup guide and one-site license.',
        'seo_keywords': ['interior design website template', 'interior studio website kit', 'editable interior designer portfolio', 'responsive HTML website template', 'interior design landing page'],
        'ai_summary': 'Downloadable website kit for an interior design studio: responsive HTML, CSS and JavaScript; editable brand, contact details and colors; five original SVG illustrations; setup instructions; and a non-exclusive one-site/client license. Demo photographs are excluded.',
        'language': 'en',
    },
}

OLD_SCHEMA = '''    schema = {"@context":"https://schema.org", "@type":"Product", "name":product.title,
              "url":f"https://mojplaywin.com/store/product/{product.pk}/",
              "description":str(summary or "Digital product listed in the MojPlayWin catalog.")}
    # Do not publish Offer/availability/payment claims until checkout is verified.
'''
NEW_SCHEMA = '''    schema = {"@context":"https://schema.org", "@type":"Product", "name":product.title,
              "url":f"https://mojplaywin.com/store/product/{product.pk}/",
              "description":str(summary or "Digital product listed in the MojPlayWin catalog."),
              "offers":{"@type":"Offer", "price":str(product.price), "priceCurrency":str(product.currency),
                       "availability":"https://schema.org/InStock",
                       "url":f"https://mojplaywin.com/store/product/{product.pk}/"}}
'''
OLD_META = '''{% block meta_description %}{{ product.metadata.summary|default:"Explore this digital product in the MojPlayWin catalog, including details, pricing and available delivery information."|striptags|truncatechars:155 }}{% endblock %}'''
NEW_META = '''{% block meta_description %}{{ product.metadata.seo_description|default:product.metadata.summary|default:"Explore this digital product in the MojPlayWin catalog, including details, pricing and available delivery information."|striptags|truncatechars:155 }}{% endblock %}'''

def fail(msg):
    raise RuntimeError(msg)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def expected_products(Product):
    rows = {}
    for pk, (title, price) in EXPECTED.items():
        p = Product.objects.select_for_update().get(pk=pk)
        if str(p.title) != title or str(p.price) != price or str(p.currency) != 'USD' or not p.active:
            fail(f'Product identity/price guard failed for {pk}')
        if not isinstance(p.metadata, dict):
            fail(f'Product metadata is not a JSON object for {pk}')
        rows[pk] = p
    return rows

def backup_dir(run):
    if not re.fullmatch(r'[0-9]{8,20}', run):
        fail('Invalid release run id')
    return HOME / f'.mpw-product-seo-{run}'

def atomic(path, raw):
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix='.mpw-seo-atomic-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def schema_patch(source):
    if source.count(NEW_SCHEMA) == 1 and OLD_SCHEMA not in source:
        return source
    if source.count(OLD_SCHEMA) != 1:
        fail('Product schema source changed; refusing broad edit')
    return source.replace(OLD_SCHEMA, NEW_SCHEMA, 1)

def template_patch(source):
    if source.count(NEW_META) == 1 and OLD_META not in source:
        return source
    if source.count(OLD_META) != 1: fail('Product template meta description changed; refusing broad edit')
    return source.replace(OLD_META, NEW_META, 1)

def run_release(run):
    if ROOT.is_symlink() or not ROOT.is_dir() or VIEW.is_symlink() or not VIEW.is_file() or TEMPLATE.is_symlink() or not TEMPLATE.is_file():
        fail('Unexpected Django checkout or view file')
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.db import transaction
    from django.test import Client
    from core.models import Product

    old_view = VIEW.read_bytes()
    new_view = schema_patch(old_view.decode('utf-8')).encode('utf-8')
    old_template = TEMPLATE.read_bytes()
    new_template = template_patch(old_template.decode('utf-8')).encode('utf-8')
    original_metadata = {}
    d = backup_dir(run)
    if d.exists() or d.is_symlink(): fail('Release backup already exists')

    with transaction.atomic():
        rows = expected_products(Product)
        for pk, p in rows.items(): original_metadata[str(pk)] = p.metadata

    d.mkdir(mode=0o700)
    for name, raw in [('brand_views.py.bak', old_view), ('product.html.bak', old_template),
                      ('metadata.json.bak', json.dumps(original_metadata, ensure_ascii=False, sort_keys=True).encode('utf-8'))]:
        with (d / name).open('xb') as f:
            os.fchmod(f.fileno(), 0o600); f.write(raw); f.flush(); os.fsync(f.fileno())
    manifest = {'run': run, 'view_before': digest(old_view), 'view_after': digest(new_view),
                'template_before': digest(old_template), 'template_after': digest(new_template), 'products': list(EXPECTED)}
    with (d / 'manifest.json').open('x') as f:
        os.fchmod(f.fileno(), 0o600); json.dump(manifest, f, sort_keys=True); f.flush(); os.fsync(f.fileno())

    try:
        with transaction.atomic():
            rows = expected_products(Product)
            for pk, p in rows.items():
                updated = dict(p.metadata)
                updated.update(CONTENT[pk])
                p.metadata = updated
                p.save(update_fields=['metadata'])
        if digest(VIEW.read_bytes()) != manifest['view_before']: fail('Concurrent view edit detected')
        if digest(TEMPLATE.read_bytes()) != manifest['template_before']: fail('Concurrent template edit detected')
        atomic(VIEW, new_view)
        atomic(TEMPLATE, new_template)
        import py_compile
        py_compile.compile(str(VIEW), doraise=True)
        client = Client(HTTP_HOST='mojplaywin.com')
        checks = []
        for pk, (title, price) in EXPECTED.items():
            resp = client.get(f'/store/product/{pk}/', HTTP_HOST='mojplaywin.com', follow=True)
            if resp.status_code != 200: fail(f'Product route {pk} returned {resp.status_code}')
            body = resp.content.decode('utf-8')
            if title not in body or CONTENT[pk]['seo_description'] not in body:
                fail(f'Product page metadata missing for {pk}')
            scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
            schemas = [json.loads(script) for script in scripts]
            schema = next((item for item in schemas if item.get('@type') == 'Product'), None)
            if schema is None: fail(f'Product JSON-LD missing for {pk}')
            offer = schema.get('offers', {})
            try: numeric_price_ok = Decimal(str(offer.get('price'))) == Decimal(price)
            except (InvalidOperation, TypeError): numeric_price_ok = False
            if schema.get('@type') != 'Product' or not numeric_price_ok or offer.get('priceCurrency') != 'USD':
                fail(f'Product JSON-LD offer check failed for {pk}')
            checks.append({'id': pk, 'status': resp.status_code, 'price': offer['price'], 'schema': 'Product+Offer'})
        print('MPW_PRODUCT_SEO_RELEASE=' + json.dumps({'run':run,'checks':checks,'metadata_only_product_rows':list(EXPECTED)}, ensure_ascii=False, sort_keys=True))
    except BaseException:
        with transaction.atomic():
            for pk, meta in original_metadata.items():
                p = Product.objects.select_for_update().get(pk=int(pk)); p.metadata = meta; p.save(update_fields=['metadata'])
        if VIEW.exists() and digest(VIEW.read_bytes()) == manifest['view_after']:
            atomic(VIEW, old_view)
        if TEMPLATE.exists() and digest(TEMPLATE.read_bytes()) == manifest['template_after']:
            atomic(TEMPLATE, old_template)
        raise

def selftest():
    assert all(len(x['seo_description']) <= 160 for x in CONTENT.values())
    patched = schema_patch(OLD_SCHEMA)
    assert OLD_SCHEMA not in patched and '"offers"' in patched
    assert template_patch(OLD_META).count(NEW_META) == 1
    print('MPW_PRODUCT_SEO_SELFTEST=PASS')

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest': selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish': run_release(sys.argv[2])
    else: raise SystemExit('Usage: selftest | publish RUN_ID')

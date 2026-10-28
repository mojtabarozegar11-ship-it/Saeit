#!/usr/bin/env python3
"""Bounded MojPlayWin SEO metadata and Product JSON-LD release."""
from __future__ import annotations
import hashlib, json, os, re, stat, sys, tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path('/home/zomorod2/Saeit-staging')
VIEW = ROOT / 'core/brand_views.py'
TEMPLATE = ROOT / 'core/templates/brands/mojplaywin/product.html'
BASE_TEMPLATE = ROOT / 'core/templates/brands/mojplaywin/base.html'
SITEMAP_VIEW = ROOT / 'core/brand_seo_views.py'
HOME = Path('/home/zomorod2')
STATIC_ROOT = ROOT / 'staticfiles'
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
        'poster_url': 'https://mojplaywin.com/static/site/mojplaywin-products/chess-improvement.webp',
        'poster_alt': 'Premium chess improvement training guide poster with a chessboard, knight and study workbook',
    },
    225: {
        'summary': 'Read Taniya and the Little Baker Worms, an English rhythmic read-aloud picture book presented as a 40-page illustrated PDF. The digital book includes its front and back covers and is designed for shared story time and young readers.',
        'seo_description': 'Taniya and the Little Baker Worms is a 40-page illustrated PDF picture book with an English rhythmic read-aloud story and covers.',
        'seo_keywords': ['illustrated picture book PDF', 'read-aloud story for children', 'English rhythmic storybook', '40-page digital picture book', 'Taniya and the Little Baker Worms'],
        'ai_summary': 'A digital English-language picture book in PDF format, with 40 illustrated pages, a rhythmic read-aloud story, and front and back covers.',
        'language': 'en',
        'poster_url': 'https://mojplaywin.com/static/site/mojplaywin-products/taniya-baker-worms.webp',
        'poster_alt': 'Taniya and cheerful little baker worms make bread together in a sunny storybook kitchen',
    },
    879: {
        'summary': 'Launch a polished interior-design studio website with the Atelier Interior client-ready kit. The downloadable ZIP includes responsive HTML, CSS and JavaScript, editable brand and contact details, five original SVG interior illustrations, setup instructions, and a non-exclusive one-site/client license. Demo photographs are not included.',
        'seo_description': 'A responsive interior design website template kit with editable branding, five SVG illustrations, source files, setup guide and one-site license.',
        'seo_keywords': ['interior design website template', 'interior studio website kit', 'editable interior designer portfolio', 'responsive HTML website template', 'interior design landing page'],
        'ai_summary': 'Downloadable website kit for an interior design studio: responsive HTML, CSS and JavaScript; editable brand, contact details and colors; five original SVG illustrations; setup instructions; and a non-exclusive one-site/client license. Demo photographs are excluded.',
        'language': 'en',
        'poster_url': 'https://mojplaywin.com/static/site/mojplaywin-products/atelier-interior-kit.webp',
        'poster_alt': 'Warm minimalist interior design studio scene for the Atelier Interior website kit',
    },
}

POSTER_FILES = {
    'chess-improvement.webp': 'a0705291d9eb90408b4d5d8b696fbe0dc849ff7d250238372b6c3dc6b6f2cd55',
    'taniya-baker-worms.webp': 'd1f75e0605a952da36458a8e4c010852e6a7972184473e1f013824312132cf6b',
    'atelier-interior-kit.webp': '0659b0b964748d842546805a40d889d1196c02d1cf9b7ee8cdb780de5f8cb83d',
}
POSTER_DIR = STATIC_ROOT / 'site/mojplaywin-products'

OLD_SCHEMA = '''    schema = {"@context":"https://schema.org", "@type":"Product", "name":product.title,
              "url":f"https://mojplaywin.com/store/product/{product.pk}/",
              "description":str(summary or "Digital product listed in the MojPlayWin catalog.")}
    # Do not publish Offer/availability/payment claims until checkout is verified.
'''
CURRENT_SCHEMA = '''    schema = {"@context":"https://schema.org", "@type":"Product", "name":product.title,
              "url":f"https://mojplaywin.com/store/product/{product.pk}/",
              "description":str(summary or "Digital product listed in the MojPlayWin catalog."),
              "offers":{"@type":"Offer", "price":str(product.price), "priceCurrency":str(product.currency),
                       "availability":"https://schema.org/InStock",
                       "url":f"https://mojplaywin.com/store/product/{product.pk}/"}}
'''
NEW_SCHEMA = CURRENT_SCHEMA + '''    poster = (product.metadata or {}).get("poster_url") if isinstance(product.metadata, dict) else None
    if isinstance(poster, str) and poster.startswith("https://mojplaywin.com/static/site/mojplaywin-products/"):
        schema["image"] = [poster]
'''
OLD_PUBLIC_GUARD = '''    product=get_object_or_404(Product, pk=pk, active=True)
    summary = (product.metadata or {}).get("summary") if isinstance(product.metadata, dict) else None
'''
NEW_PUBLIC_GUARD = '''    product=get_object_or_404(Product, pk=pk, active=True)
    from mpw_commerce.buyer_orders import _eligible
    import os
    canary_ids = {779}
    configured_canary = os.getenv("MPW_TRX_CANARY_PRODUCT_ID", "")
    if configured_canary.isdigit(): canary_ids.add(int(configured_canary))
    if product.pk in canary_ids or not _eligible(product): raise Http404
    summary = (product.metadata or {}).get("summary") if isinstance(product.metadata, dict) else None
'''
OLD_META = '''{% block meta_description %}{{ product.metadata.summary|default:"Explore this digital product in the MojPlayWin catalog, including details, pricing and available delivery information."|striptags|truncatechars:155 }}{% endblock %}'''
NEW_META = '''{% block meta_description %}{{ product.metadata.seo_description|default:product.metadata.summary|default:"Explore this digital product in the MojPlayWin catalog, including details, pricing and available delivery information."|striptags|truncatechars:155 }}{% endblock %}'''
OLD_HERO = '<h1>{{ product.title }}</h1><p>{{ product.metadata.summary|default:"A verified product in the MojPlayWin global catalog." }}</p>'
NEW_HERO = '''<h1>{{ product.title }}</h1>{% if product.metadata.poster_url %}<figure class="mpw-product-poster" style="margin:24px auto;max-width:360px"><img src="{{ product.metadata.poster_url }}" alt="{{ product.metadata.poster_alt|default:product.title }}" width="720" height="900" loading="eager" fetchpriority="high" decoding="async" style="display:block;width:100%;height:auto;max-height:450px;object-fit:cover;border-radius:18px;box-shadow:0 18px 55px #0005"></figure>{% endif %}<p>{{ product.metadata.summary|default:"A verified product in the MojPlayWin global catalog." }}</p>'''
OLD_BASE_OG = '<meta property="og:image" content="https://mojplaywin.com/static/site/mojplaywin-coin-logo.png"><meta name="twitter:image" content="https://mojplaywin.com/static/site/mojplaywin-coin-logo.png">'
NEW_BASE_OG = '<meta property="og:image" content="{% if product and product.metadata.poster_url %}{{ product.metadata.poster_url }}{% else %}https://mojplaywin.com/static/site/mojplaywin-coin-logo.png{% endif %}">{% if product and product.metadata.poster_alt %}<meta property="og:image:alt" content="{{ product.metadata.poster_alt }}">{% endif %}<meta name="twitter:image" content="{% if product and product.metadata.poster_url %}{{ product.metadata.poster_url }}{% else %}https://mojplaywin.com/static/site/mojplaywin-coin-logo.png{% endif %}"><meta name="twitter:title" content="{% if product and product.title %}{{ product.title }} | MojPlayWin{% endif %}"><meta name="twitter:description" content="{% if product and product.metadata.seo_description %}{{ product.metadata.seo_description|striptags|truncatechars:155 }}{% endif %}">'
OLD_BASE_DESCRIPTION = '<meta name="description" content="{% block meta_description %}Explore virtual products, original games, AI tools, software and digital experiences from MojPlayWin, a global digital innovation platform.{% endblock %}">'
NEW_BASE_DESCRIPTION = OLD_BASE_DESCRIPTION + '{% if product and product.metadata.seo_keywords %}<meta name="keywords" content="{{ product.metadata.seo_keywords|join:", " }}">{% endif %}'
OLD_SITEMAP = '''        # Only products marked active are included; inactive drafts remain unlisted.
        product_ids = Product.objects.filter(active=True).order_by('pk').values_list('pk', flat=True).iterator(chunk_size=500)
        paths.extend(f"store/product/{pk}/" for pk in product_ids)
'''
NEW_SITEMAP = '''        # MPW_PUBLIC_PRODUCT_SITEMAP_ELIGIBLE_ONLY_20261023
        from mpw_commerce.buyer_orders import _eligible
        import os
        canary_ids = {779}
        configured_canary = os.getenv("MPW_TRX_CANARY_PRODUCT_ID", "")
        if configured_canary.isdigit(): canary_ids.add(int(configured_canary))
        for product in Product.objects.filter(active=True).order_by("pk").iterator(chunk_size=500):
            if product.pk not in canary_ids and _eligible(product):
                paths.append(f"store/product/{product.pk}/")
'''

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
    if source.count(NEW_PUBLIC_GUARD) == 1 and OLD_PUBLIC_GUARD not in source:
        guard_source = source
    elif OLD_PUBLIC_GUARD not in source and NEW_PUBLIC_GUARD not in source:
        # Keep focused self-tests (which only pass the schema block) useful.
        guard_source = source
    else:
        if source.count(OLD_PUBLIC_GUARD) != 1: fail('Public product guard source changed; refusing broad edit')
        guard_source = source.replace(OLD_PUBLIC_GUARD, NEW_PUBLIC_GUARD, 1)
    if source.count(NEW_SCHEMA) == 1 and OLD_SCHEMA not in source and CURRENT_SCHEMA not in source:
        return guard_source
    if source.count(CURRENT_SCHEMA) == 1:
        return guard_source.replace(CURRENT_SCHEMA, NEW_SCHEMA, 1)
    if source.count(OLD_SCHEMA) != 1:
        fail('Product schema source changed; refusing broad edit')
    return guard_source.replace(OLD_SCHEMA, NEW_SCHEMA, 1)

def template_patch(source):
    if source.count(NEW_META) == 1 and OLD_META not in source:
        pass
    elif source.count(OLD_META) == 1:
        source = source.replace(OLD_META, NEW_META, 1)
    else: fail('Product template meta description changed; refusing broad edit')
    if source.count(NEW_HERO) == 1 and OLD_HERO not in source: return source
    if source.count(OLD_HERO) != 1: fail('Product hero source changed; refusing broad edit')
    return source.replace(OLD_HERO, NEW_HERO, 1)

def base_template_patch(source):
    if source.count(NEW_BASE_OG) != 1:
        if source.count(OLD_BASE_OG) != 1: fail('Shared social image source changed; refusing broad edit')
        source = source.replace(OLD_BASE_OG, NEW_BASE_OG, 1)
    if NEW_BASE_DESCRIPTION not in source:
        if source.count(OLD_BASE_DESCRIPTION) != 1: fail('Shared description source changed; refusing broad edit')
        source = source.replace(OLD_BASE_DESCRIPTION, NEW_BASE_DESCRIPTION, 1)
    return source

def sitemap_patch(source):
    if source.count(NEW_SITEMAP) == 1 and OLD_SITEMAP not in source: return source
    if source.count(OLD_SITEMAP) != 1: fail('Product sitemap source changed; refusing broad edit')
    return source.replace(OLD_SITEMAP, NEW_SITEMAP, 1)

def verify_posters():
    if STATIC_ROOT.is_symlink() or not STATIC_ROOT.is_dir() or POSTER_DIR.is_symlink() or not POSTER_DIR.is_dir():
        fail('Expected static product poster directory is missing or unsafe')
    for name, expected in POSTER_FILES.items():
        path = POSTER_DIR / name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            fail(f'Product poster missing or checksum mismatch: {name}')

def run_release(run):
    if ROOT.is_symlink() or not ROOT.is_dir() or VIEW.is_symlink() or not VIEW.is_file() or TEMPLATE.is_symlink() or not TEMPLATE.is_file() or BASE_TEMPLATE.is_symlink() or not BASE_TEMPLATE.is_file() or SITEMAP_VIEW.is_symlink() or not SITEMAP_VIEW.is_file():
        fail('Unexpected Django checkout or view file')
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.db import transaction
    from django.test import Client
    from django.conf import settings
    from core.models import Product

    if Path(settings.STATIC_ROOT).resolve() != STATIC_ROOT.resolve(): fail('Static root changed; refusing to publish poster assets')
    verify_posters()

    old_view = VIEW.read_bytes()
    new_view = schema_patch(old_view.decode('utf-8')).encode('utf-8')
    old_template = TEMPLATE.read_bytes()
    new_template = template_patch(old_template.decode('utf-8')).encode('utf-8')
    old_base_template = BASE_TEMPLATE.read_bytes()
    new_base_template = base_template_patch(old_base_template.decode('utf-8')).encode('utf-8')
    old_sitemap = SITEMAP_VIEW.read_bytes()
    new_sitemap = sitemap_patch(old_sitemap.decode('utf-8')).encode('utf-8')
    original_metadata = {}
    d = backup_dir(run)
    if d.exists() or d.is_symlink(): fail('Release backup already exists')

    with transaction.atomic():
        rows = expected_products(Product)
        for pk, p in rows.items(): original_metadata[str(pk)] = p.metadata

    d.mkdir(mode=0o700)
    for name, raw in [('brand_views.py.bak', old_view), ('product.html.bak', old_template), ('base.html.bak', old_base_template), ('brand_seo_views.py.bak', old_sitemap),
                      ('metadata.json.bak', json.dumps(original_metadata, ensure_ascii=False, sort_keys=True).encode('utf-8'))]:
        with (d / name).open('xb') as f:
            os.fchmod(f.fileno(), 0o600); f.write(raw); f.flush(); os.fsync(f.fileno())
    manifest = {'run': run, 'view_before': digest(old_view), 'view_after': digest(new_view),
                'template_before': digest(old_template), 'template_after': digest(new_template),
                'base_template_before': digest(old_base_template), 'base_template_after': digest(new_base_template),
                'sitemap_before': digest(old_sitemap), 'sitemap_after': digest(new_sitemap), 'products': list(EXPECTED)}
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
        if digest(BASE_TEMPLATE.read_bytes()) != manifest['base_template_before']: fail('Concurrent shared-template edit detected')
        if digest(SITEMAP_VIEW.read_bytes()) != manifest['sitemap_before']: fail('Concurrent sitemap view edit detected')
        atomic(VIEW, new_view)
        atomic(TEMPLATE, new_template)
        atomic(BASE_TEMPLATE, new_base_template)
        atomic(SITEMAP_VIEW, new_sitemap)
        import py_compile
        py_compile.compile(str(VIEW), doraise=True)
        py_compile.compile(str(SITEMAP_VIEW), doraise=True)
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
            poster = CONTENT[pk]['poster_url']
            if poster not in body or CONTENT[pk]['poster_alt'] not in body or schema.get('image') != [poster]:
                fail(f'Product poster markup/schema missing for {pk}')
            checks.append({'id': pk, 'status': resp.status_code, 'price': offer['price'], 'schema': 'Product+Offer+Image', 'poster': poster})
        hidden_checks = {}
        for pk in (779, 968, 969, 970, 971, 972):
            resp = client.get(f'/store/product/{pk}/', HTTP_HOST='mojplaywin.com', follow=True)
            hidden_checks[str(pk)] = resp.status_code
            if resp.status_code != 404: fail(f'Ineligible product route {pk} should return 404, got {resp.status_code}')
        sitemap_resp = client.get('/sitemap.xml', HTTP_HOST='mojplaywin.com', follow=True)
        import xml.etree.ElementTree as ET
        locations = [node.text for node in ET.fromstring(sitemap_resp.content).iter() if node.tag.endswith('loc')]
        expected_urls = {f'https://mojplaywin.com/store/product/{pk}/' for pk in EXPECTED}
        if sitemap_resp.status_code != 200 or not expected_urls.issubset(set(locations)):
            fail('Eligible product URLs missing from sitemap')
        if any(f'https://mojplaywin.com/store/product/{pk}/' in locations for pk in (779, 968, 969, 970, 971, 972)):
            fail('Canary or ineligible product URL remains in sitemap')
        print('MPW_PRODUCT_SEO_RELEASE=' + json.dumps({'run':run,'checks':checks,'ineligible_routes_404':hidden_checks,'sitemap_eligible_products':len(expected_urls),'test_or_ineligible_ids_removed':[779,968,969,970,971,972]}, ensure_ascii=False, sort_keys=True))
    except BaseException:
        with transaction.atomic():
            for pk, meta in original_metadata.items():
                p = Product.objects.select_for_update().get(pk=int(pk)); p.metadata = meta; p.save(update_fields=['metadata'])
        if VIEW.exists() and digest(VIEW.read_bytes()) == manifest['view_after']:
            atomic(VIEW, old_view)
        if TEMPLATE.exists() and digest(TEMPLATE.read_bytes()) == manifest['template_after']:
            atomic(TEMPLATE, old_template)
        if BASE_TEMPLATE.exists() and digest(BASE_TEMPLATE.read_bytes()) == manifest['base_template_after']:
            atomic(BASE_TEMPLATE, old_base_template)
        if SITEMAP_VIEW.exists() and digest(SITEMAP_VIEW.read_bytes()) == manifest['sitemap_after']:
            atomic(SITEMAP_VIEW, old_sitemap)
        raise

def selftest():
    assert all(len(x['seo_description']) <= 160 for x in CONTENT.values())
    patched = schema_patch(OLD_SCHEMA)
    assert OLD_SCHEMA not in patched and '"offers"' in patched
    guarded = schema_patch(OLD_PUBLIC_GUARD + OLD_SCHEMA)
    assert NEW_PUBLIC_GUARD in guarded and NEW_SCHEMA in guarded
    patched_template = template_patch(OLD_META + OLD_HERO)
    assert patched_template.count(NEW_META) == 1 and patched_template.count(NEW_HERO) == 1
    assert OLD_BASE_OG not in base_template_patch(OLD_BASE_OG + OLD_BASE_DESCRIPTION)
    assert OLD_SITEMAP not in sitemap_patch(OLD_SITEMAP) and 'MPW_PUBLIC_PRODUCT_SITEMAP_ELIGIBLE_ONLY_20261023' in sitemap_patch(OLD_SITEMAP)
    print('MPW_PRODUCT_SEO_SELFTEST=PASS')

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest': selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish': run_release(sys.argv[2])
    else: raise SystemExit('Usage: selftest | publish RUN_ID')

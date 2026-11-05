#!/usr/bin/env python3
"""One-off exact-hash, reversible staging root and service-card alignment."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
CANONICAL = HOME / 'Saeit-staging'
SNAPSHOT = CANONICAL / 'admin-smoke/ab090d03f5bc-38498776878'
WEBROOT = HOME / 'Saeit-staging-web'
HTACCESS = WEBROOT / '.htaccess'
TEMPLATE = CANONICAL / 'core/templates/core/services.html'
BRAND = CANONICAL / 'core/brand.py'
BACKUP_ROOT = HOME / '.private/staging-services-backups'
SELECTOR = '/usr/sbin/cloudlinux-selector'
OLD_HTACCESS_SHA = '1eb2b0c7c7e056f5121380d1f83cdc8b6ae49524e249d0a117a7f227b772b361'
OLD_TEMPLATE_SHA = '195994985017c1cbc0247969f9215fbcb34d4cc3bd4f8aeeac92ff270d7350bc'
OLD_BRAND_SHA = 'babf9b1870f61d5074ecc5efdb112c85fdb7ac90ca6aa9212b2a63c6ec0d6658'
EXPECTED_ROUTE_SHA = '71158d0dc33c692bf54de0fb1cf9d5c796ca6c199dfd2cb83fdadab2bcbf832e'
EXPECTED_SERVICES_VIEW_SHA = 'a9373f9c88b74569900bf3185b5393096cb5146a14e9b6b990c5b9d32b9919c3'
EXPECTED_CANONICAL_WSGI_SHA = '4bdd0561fd23f6ba60e2bf0aaca4d5ed7b6528c1af588a2bfda2958801cc0cd9'
BRAND_LINE = '    "staging.zomorodmelal.ir": Brand("mojplaywin", "MojPlayWin", "mojplaywin.com", "brands/mojplaywin/home.html"),\n'
OLD_ROOT_LINE = 'PassengerAppRoot ' + str(SNAPSHOT)
NEW_ROOT_LINE = 'PassengerAppRoot ' + str(CANONICAL)

CHANGES = {
    '<article class="services-domain services-domain-market"><div class="services-no">08</div><span>MARKET · COMMERCE</span><h2>بازار</h2><p>محصول، سفارش، فروش، مزایده و اتصال زنجیره‌های شرکت به بازار.</p><a href="/market/">ورود به بازار ↗</a></article>':
    '<article class="services-domain services-domain-research"><div class="services-no">08</div><span>RESEARCH · PROJECTS</span><h2>پژوهش‌های کاربردی</h2><p>آشنایی با طرح‌های پژوهشی، ژنتیکی و توسعهٔ فناوری شرکت در درگاه رسمی.</p><a href="https://zomorodmelal.ir/research/projects/">مشاهدهٔ طرح‌های پژوهشی ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">12</div><span>ACADEMY · LEARNING</span><h2>آموزش</h2><p>آموزش و مهارت برای ورود، رشد و استفاده حرفه‌ای از اکوسیستم خدماتی.</p><a href="/education/">ورود به آموزش ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">12</div><span>TOOLS · APPLICATIONS</span><h2>ابزارهای کاربردی</h2><p>دسترسی به ابزارها و برنامه‌های رایگانِ منتشرشده در وب‌سایت رسمی شرکت.</p><a href="https://zomorodmelal.ir/apps/">مشاهدهٔ ابزارهای کاربردی ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">13</div><span>AI · INTELLIGENCE</span><h2>هوش مصنوعی</h2><p>ابزارها و عامل‌های هوشمند برای پژوهش، تحلیل و اجرای کنترل‌شده.</p><a href="/agents/">ورود به هوش مصنوعی ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">13</div><span>NEWS · BULLETIN</span><h2>خبرنامهٔ شرکت</h2><p>مطالعهٔ مطالب و اطلاعیه‌های عمومی منتشرشده در درگاه رسمی زمرد ملل.</p><a href="https://zomorodmelal.ir/newsletter/">ورود به خبرنامه ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">14</div><span>KNOWLEDGE · ENCYCLOPEDIA</span><h2>دانشنامه</h2><p>مرجع ساختاریافته دانش، مفاهیم و محتوای قابل استفاده پلتفرم.</p><a href="/knowledge/">ورود به دانشنامه ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">14</div><span>CONTACT · COLLABORATION</span><h2>ارتباط و همکاری</h2><p>مسیر رسمی تماس با شرکت و بررسی فرصت‌های همکاری تخصصی.</p><a href="https://zomorodmelal.ir/contact/">راه‌های ارتباط رسمی ↗</a></article>',
}

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def targets() -> tuple[Path, Path, Path]:
    return (HTACCESS, TEMPLATE, BRAND)

def valid_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and not path.parent.is_symlink()

def read_versions() -> tuple[bytes, bytes, bytes]:
    expected = (OLD_HTACCESS_SHA, OLD_TEMPLATE_SHA, OLD_BRAND_SHA)
    result = []
    for path, sha in zip(targets(), expected):
        if not valid_file(path) or digest(path.read_bytes()) != sha:
            raise RuntimeError('EXACT_SOURCE_HASH_OR_PATH_MISMATCH:' + path.name)
        result.append(path.read_bytes())
    return tuple(result)

def selector_get() -> dict:
    if not Path(SELECTOR).is_file():
        raise RuntimeError('SELECTOR_NOT_AVAILABLE')
    p = subprocess.run(
        [SELECTOR, 'get', '--json', '--interpreter', 'python', '--user', 'zomorod2'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=22)
    if p.returncode != 0 or len(p.stdout) > 1300000:
        raise RuntimeError('SELECTOR_GET_UNAVAILABLE')
    return json.loads(p.stdout.decode('utf-8', 'replace'))

def assert_registered_staging() -> None:
    doc = selector_get()
    if doc.get('result') != 'success' or doc.get('passenger_active') is not True:
        raise RuntimeError('SELECTOR_NOT_ACTIVE')
    found = []
    def walk(node: object, parent: str = '') -> None:
        if isinstance(node, dict):
            keys = {str(k).lower().replace('-', '_'): v for k, v in node.items()}
            if 'app_uri' in keys and 'app_status' in keys:
                found.append((parent, keys.get('domain'), keys.get('app_uri'), keys.get('app_status')))
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    walk(v, str(k))
        elif isinstance(node, list):
            for v in node[:150]:
                walk(v, parent)
    walk(doc)
    exact = [r for r in found if r[0] == 'Saeit-staging'
             and r[1] == 'staging.zomorodmelal.ir'
             and r[2] == '/' and r[3] == 'started']
    if len(exact) != 1:
        raise RuntimeError('STAGING_REGISTERED_APP_NOT_UNIQUE')
    if any(r[0] == 'Saeit-staging/admin-smoke/ab090d03f5bc-38498776878' for r in found):
        raise RuntimeError('SNAPSHOT_ALREADY_REGISTERED')

def preflight() -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('CPANEL_IDENTITY_MISMATCH')
    if any(p.is_symlink() or not p.is_dir() for p in (CANONICAL, SNAPSHOT, WEBROOT)):
        raise RuntimeError('STAGING_ROOT_INVALID')
    mainht = HOME / 'public_html/.htaccess'
    mpwht = HOME / 'mojplaywin.com/.htaccess'
    if not all(valid_file(p) for p in (mainht, mpwht)):
        raise RuntimeError('SIBLING_VHOST_UNAVAILABLE')
    if 'PassengerAppRoot "' + str(HOME / 'Saeit') + '"' not in mainht.read_text('utf-8', 'replace'):
        raise RuntimeError('MAIN_APP_ROOT_CHANGED')
    if 'PassengerAppRoot ' + str(HOME / 'mojplaywin.com') not in mpwht.read_text('utf-8', 'replace'):
        raise RuntimeError('MPW_APP_ROOT_CHANGED')
    old_ht, old_template, old_brand = read_versions()
    other_sources = (
        (CANONICAL / 'config/urls.py', EXPECTED_ROUTE_SHA),
        (CANONICAL / 'core/services_views.py', EXPECTED_SERVICES_VIEW_SHA),
        (CANONICAL / 'passenger_wsgi.py', EXPECTED_CANONICAL_WSGI_SHA),
    )
    if any(not valid_file(p) or digest(p.read_bytes()) != sha
           for p, sha in other_sources):
        raise RuntimeError('CANONICAL_ROUTING_OR_WSGI_HAS_CHANGED')
    revised = old_template.decode('utf-8')
    for source, target in CHANGES.items():
        if revised.count(source) != 1:
            raise RuntimeError('EXPECTED_SERVICE_CARD_ANCHOR_MISSING')
        revised = revised.replace(source, target, 1)
    if revised.count('<article') != old_template.decode('utf-8').count('<article'):
        raise RuntimeError('ARTICLE_COUNT_CHANGED')
    new_template = revised.encode('utf-8')
    if digest(new_template) != 'e0de859b639bc56f7b3c58ccefdfd8c8dff2e5a18cf987837aa83a51ad200622':
        raise RuntimeError('REVISED_TEMPLATE_HASH_MISMATCH')
    oldbrand = old_brand.decode('utf-8')
    if oldbrand.count(BRAND_LINE) != 1:
        raise RuntimeError('STAGING_BRAND_ANCHOR_MISSING')
    new_brand = oldbrand.replace(BRAND_LINE, '', 1).encode('utf-8')
    oldweb = old_ht.decode('utf-8')
    old_root_match = re.compile(r'(?m)^' + re.escape(OLD_ROOT_LINE) + r'$')
    new_root_match = re.compile(r'(?m)^' + re.escape(NEW_ROOT_LINE) + r'$')
    if len(old_root_match.findall(oldweb)) != 1 or new_root_match.search(oldweb):
        raise RuntimeError('PASSENGER_WEBROOT_ANCHOR_MISMATCH')
    new_ht = old_root_match.sub(lambda _: NEW_ROOT_LINE, oldweb, count=1).encode('utf-8')
    assert_registered_staging()
    with urlopen('https://staging.zomorodmelal.ir/?zm_before_align=' +
                 str(time.time_ns()), timeout=12) as response:
        old_page = response.read(180000)
        if response.status != 200 or digest(old_page) != (
                '5ca1cb617d9875bfab1ac9a3d5a9258840f4778b06e16d023d907791806d246c'):
            raise RuntimeError('PUBLIC_STAGING_SOURCE_DRIFT')
    return old_ht, old_template, old_brand, new_ht, new_template, new_brand

def backup_folder(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUP_ROOT / ('run-' + run_id + '-canonical-root')

def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix='.zm-root-align-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if not valid_file(path):
            raise RuntimeError('TARGET_CHANGED_DURING_WRITE')
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)

def selector_restart() -> None:
    cmd = [SELECTOR, 'restart', '--json', '--interpreter', 'python',
           '--user', 'zomorod2', '--app-root', 'Saeit-staging']
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=42, check=False)
    if p.returncode != 0 or len(p.stdout) > 100000:
        raise RuntimeError('STAGING_SELECTOR_RESTART_FAILED')
    doc = json.loads(p.stdout.decode('utf-8', 'replace'))
    if doc.get('result') != 'success':
        raise RuntimeError('STAGING_SELECTOR_RESTART_REJECTED')
    print('STAGING_ONLY_CLOUDLINUX_RESTART=SUCCESS', flush=True)

def touch_canonical_restart() -> None:
    tmp = CANONICAL / 'tmp'
    marker = tmp / 'restart.txt'
    if tmp.is_symlink() or not tmp.is_dir() or marker.is_symlink():
        raise RuntimeError('STAGING_RESTART_MARKER_UNSAFE')
    marker.touch(exist_ok=True)

def verify_staging() -> None:
    expected = ('پژوهش‌های کاربردی', 'ابزارهای کاربردی',
                'خبرنامهٔ شرکت', 'ارتباط و همکاری')
    required_urls = ('https://zomorodmelal.ir/research/projects/',
                     'https://zomorodmelal.ir/apps/',
                     'https://zomorodmelal.ir/newsletter/',
                     'https://zomorodmelal.ir/contact/')
    hashes = []
    # Allow application-specific restart to settle without a server-wide recycle.
    for attempt in range(18):
        try:
            address = 'https://staging.zomorodmelal.ir/?zm_align_warm=' + str(attempt)
            with urlopen(Request(address, headers={'Cache-Control': 'no-cache, no-store',
                'Pragma': 'no-cache', 'Connection': 'close'}), timeout=9) as response:
                data = response.read(180000).decode('utf-8', 'replace')
                heads = [re.sub('<[^>]+>', '', x).strip() for x in
                         re.findall(r'<h2[^>]*>(.*?)</h2>', data, re.I | re.S)]
                good = (response.status == 200
                    and heads.count('آموزش') == 1 and heads.count('هوش مصنوعی') == 1
                    and all(heads.count(x) == 1 for x in expected)
                    and all(u in data for u in required_urls)
                    and 'Zomorodmelal' in data)
            if good:
                break
        except Exception:
            pass
        time.sleep(3)
    else:
        raise RuntimeError('STAGING_CANONICAL_PUBLIC_NOT_UPDATED')
    for index in range(20):
        address = 'https://staging.zomorodmelal.ir/?zm_align_verify=' + str(index) + '-' + str(time.time_ns())
        with urlopen(Request(address, headers={'Cache-Control': 'no-cache, no-store',
            'Pragma': 'no-cache', 'Connection': 'close'}), timeout=11) as response:
            page = response.read(180000)
            html = page.decode('utf-8', 'replace')
            headings = [re.sub('<[^>]+>', '', x).strip() for x in
                        re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)]
            if (response.status != 200 or headings.count('آموزش') != 1
                    or headings.count('هوش مصنوعی') != 1
                    or any(headings.count(x) != 1 for x in expected)
                    or any(u not in html for u in required_urls)):
                raise RuntimeError('STAGING_PUBLIC_20_RESPONSE_MISMATCH:' + str(index))
            hashes.append(digest(page))
    if len(set(hashes)) != 1:
        raise RuntimeError('STAGING_PUBLIC_RESPONSES_NOT_UNIFORM')
    for host in ('https://zomorodmelal.ir/', 'https://mojplaywin.com/'):
        with urlopen(host, timeout=12) as response:
            if response.status != 200:
                raise RuntimeError('SIBLING_HTTP_REGRESSION')
            if host.endswith('mojplaywin.com/'):
                body = response.read(180000).decode('utf-8', 'replace')
                if 'Moj Play Win' not in body:
                    raise RuntimeError('MPW_TITLE_CHANGED')
    print('STAGING_CANONICAL_PUBLIC_VERIFIED=' + json.dumps(
        {'http_200_responses': len(hashes), 'uniform_html_sha256': hashes[0],
         'unique_titles': list(expected), 'main_and_mpw_http_200': True},
        ensure_ascii=False), flush=True)

def restore(run_id: str) -> None:
    folder = backup_folder(run_id)
    manifest = folder / 'manifest.json'
    if folder.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        raise RuntimeError('BACKUP_MANIFEST_MISSING')
    info = json.loads(manifest.read_text())
    if info.get('run_id') != run_id:
        raise RuntimeError('MANIFEST_RUN_ID_MISMATCH')
    names = ('htaccess', 'services', 'brand')
    files = targets()
    for key, path, mode in zip(names, files, info['modes']):
        old = (folder / (key + '.bak')).read_bytes()
        if digest(old) != info['old_hashes'][key]:
            raise RuntimeError('BACKUP_DIGEST_MISMATCH')
        current = digest(path.read_bytes())
        if current not in (info['old_hashes'][key], info['new_hashes'][key]):
            raise RuntimeError('CONCURRENT_SITE_EDIT_PREVENTS_ROLLBACK')
        if current != info['old_hashes'][key]:
            atomic_write(path, old, int(mode))
    try:
        touch_canonical_restart()
        selector_restart()
    finally:
        # The manager may write webroot directives during restart; keep the original root.
        old = (folder / 'htaccess.bak').read_bytes()
        if digest(HTACCESS.read_bytes()) in (info['old_hashes']['htaccess'],
                                            info['new_hashes']['htaccess']):
            atomic_write(HTACCESS, old, int(info['modes'][0]))
    if any(digest(p.read_bytes()) != info['old_hashes'][k] for p, k in zip(files, names)):
        raise RuntimeError('STAGING_ROLLBACK_POSTCHECK_FAILED')
    with urlopen('https://staging.zomorodmelal.ir/?zm_rollback=' + str(time.time_ns()),
                 timeout=12) as response:
        if response.status != 200:
            raise RuntimeError('STAGING_ROLLBACK_PUBLIC_HTTP_FAILURE')
    print('STAGING_ROOT_ALIGNMENT_ROLLBACK=RESTORED', flush=True)

def publish(run_id: str) -> None:
    version = preflight()
    originals = version[:3]
    revisions = version[3:]
    folder = backup_folder(run_id)
    if folder.exists() or folder.is_symlink() or BACKUP_ROOT.is_symlink():
        raise RuntimeError('BACKUP_COLLISION_OR_LINK')
    BACKUP_ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    names = ('htaccess', 'services', 'brand')
    modes = [stat.S_IMODE(p.stat().st_mode) for p in targets()]
    info = {'run_id': run_id, 'modes': modes,
            'old_hashes': dict(zip(names, map(digest, originals))),
            'new_hashes': dict(zip(names, map(digest, revisions)))}
    for key, content in zip(names, originals):
        path = folder / (key + '.bak')
        with path.open('xb') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    (folder / 'manifest.json').write_text(json.dumps(info))
    (folder / 'manifest.json').chmod(0o600)
    if any(digest(p.read_bytes()) != digest(v) for p, v in zip(targets(), originals)):
        raise RuntimeError('CONCURRENT_CHANGE_BEFORE_PUBLISH')
    try:
        # Keep the public vhost unchanged until the new template and routing are ready.
        for p, data, mode in zip((TEMPLATE, BRAND), revisions[1:], modes[1:]):
            atomic_write(p, data, mode)
        atomic_write(HTACCESS, revisions[0], modes[0])
        touch_canonical_restart()
        selector_restart()
        verify_staging()
    except BaseException:
        restore(run_id)
        raise
    print('STAGING_ROOT_ALIGNMENT_PUBLISHED=VERIFIED', flush=True)

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('publish', 'rollback'):
        raise SystemExit('USAGE: publish|rollback run_id')
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('CPANEL_USER_MISMATCH')
    if sys.argv[1] == 'publish':
        publish(sys.argv[2])
    else:
        if backup_folder(sys.argv[2]).is_dir():
            restore(sys.argv[2])
        else:
            print('NO_STAGING_BACKUP_CREATED_NO_ROLLBACK_NEEDED', flush=True)

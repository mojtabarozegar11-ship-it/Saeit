#!/usr/bin/env python3
"""Guarded two-file release for qualified agricultural service inquiries.

Three offer cards carry a non-sensitive whitelisted topic into existing PHP
form. The already-supported service question remains CSRF-protected, rate-
limited and stored in the current system, with its topic in a safe prefix.
No database migration, scripts, outbound messages or synthetic POST requests.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

WEB = Path('/home/zomorod2/public_html')
PRIVATE = Path('/home/zomorod2/.private')
BACKUPS = PRIVATE / 'zm-service-offer-topic-backups'
FORM = WEB / 'ask-master/index.php'
SERVICES = WEB / 'services/index.html'
FILES = {'form': FORM, 'services': SERVICES}
EXPECTED = {
    'form': 'a2d14ad6f81ae2a0ba095a1e9a42919aac97a90dd2e806f23f6dcc9361a4b176',
    'services': '9cd8b7685c56f7c90ed9c1f92fac61cf1fba42c36b242ae8d02906c3b27e0d33',
}
MARKER = 'zm-service-offer-topic-20261106'
FORM_OLD = ("echo '<label>'.($fa?'پرسش شما':'Your question').'</label>"
            '<textarea name="question" maxlength="2500" minlength="5" rows="5" required></textarea>\';')
POST_OLD = "$_POST['question']='[SERVICE_INQUIRY] '.$serviceMessage;"
POST_NEW = '''/* zm-service-offer-topic-20261106:stored-category */
    $zmAllowedServiceTags=['economics'=>'ECONOMICS','water'=>'WATER','feasibility'=>'FEASIBILITY'];
    $zmSubmittedTopic=(string)($_POST['service_topic']??'');
    $zmServicePrefix=isset($zmAllowedServiceTags[$zmSubmittedTopic])
        ? '[SERVICE_INQUIRY:'.$zmAllowedServiceTags[$zmSubmittedTopic].'] '
        : '[SERVICE_INQUIRY] ';
    $_POST['question']=$zmServicePrefix.$serviceMessage;'''
FORM_NEW = '''/* zm-service-offer-topic-20261106:visible-category */
        $zmTopicNames=[
          'economics'=>'ارزیابی اقتصادی واحد کشاورزی',
          'water'=>'مدیریت آب و منابع تولید',
          'feasibility'=>'امکان‌سنجی پروژهٔ تولیدی'
        ];
        $zmTopicHints=[
          'economics'=>'استان، نوع فعالیت، سطح یا ظرفیت، تولید، هزینه و مسئله اقتصادی شما',
          'water'=>'استان، محصول، مساحت، منبع آب، روش آبیاری و مسئله منابع',
          'feasibility'=>'استان، محصول یا طرح، ظرفیت، بازار هدف، منابع و تصمیم موردنظر'
        ];
        $zmOfferKey='';
        if($fa && $_SERVER['REQUEST_METHOD']==='GET' && (string)($_GET['service']??'')==='1'){
            $zmCandidate=(string)($_GET['topic']??'');
            if(isset($zmTopicNames[$zmCandidate]))$zmOfferKey=$zmCandidate;
        }
        if($zmOfferKey!==''){
            echo '<input type="hidden" name="service_topic" value="'.$zmOfferKey.'">';
            echo '<p class="notice" role="note">موضوع انتخابی: '.htmlspecialchars($zmTopicNames[$zmOfferKey],ENT_QUOTES,'UTF-8').'؛ برای دریافت پیشنهاد، استان، مقیاس و مسئله را شرح دهید.</p>';
        }
        $zmPlaceholder=$zmOfferKey!=='' ? ' placeholder="'.htmlspecialchars($zmTopicHints[$zmOfferKey],ENT_QUOTES,'UTF-8'). '"' : '';
        echo '<label>'.($fa?'پرسش شما':'Your question').'</label><textarea name="question" maxlength="2500" minlength="5" rows="5"'.$zmPlaceholder.' required></textarea>';'''
OFFERS = (
    ('استعلام ارزیابی اقتصادی ←', 'economics'),
    ('استعلام مدیریت منابع ←', 'water'),
    ('استعلام امکان‌سنجی ←', 'feasibility'),
)


def sha(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('OFFER_TOPIC_REFUSE_WRONG_USER')
    for path in (WEB, PRIVATE, BACKUPS, FORM.parent, SERVICES.parent, FORM, SERVICES):
        if path.is_symlink():
            raise RuntimeError('OFFER_TOPIC_REFUSE_SYMLINK')
    for path in FILES.values():
        if not path.is_file():
            raise RuntimeError('OFFER_TOPIC_REFUSE_MISSING_TARGET')
    boundary = SERVICES.parent / '.htaccess'
    if boundary.is_symlink() or not boundary.is_file() or 'PassengerEnabled off' not in boundary.read_text():
        raise RuntimeError('OFFER_TOPIC_REFUSE_NONSTATIC_SERVICES')


def transform_form(source: str) -> str:
    for item in (FORM_OLD, POST_OLD,
                 'zm-ask-master-service-kind-20261106:route',
                 'zm-specialist-intent-20261106:form'):
        if source.count(item) != 1:
            raise RuntimeError('OFFER_TOPIC_CHANGED_FORM_ANCHOR:' + item[:35])
    if MARKER in source or source.count('name="service_topic"'):
        raise RuntimeError('OFFER_TOPIC_REFUSE_REPEATED_FORM')
    updated = source.replace(POST_OLD, POST_NEW, 1).replace(FORM_OLD, FORM_NEW, 1)
    if (updated.count(MARKER) != 2 or updated.count('name="question"') != 1
            or updated.count('name="service_topic"') != 1
            or updated.count('$_POST[\'kind\']=\'question\'') != 1):
        raise RuntimeError('OFFER_TOPIC_INVALID_FORM_PATCH')
    return updated


def transform_services(source: str) -> str:
    if (source.count('zm-service-deliverables-20261106') != 2
            or source.count('zm-services-first-screen-20261106') != 1
            or MARKER in source):
        raise RuntimeError('OFFER_TOPIC_CHANGED_SERVICE_PAGE')
    result = source
    for label, topic in OFFERS:
        before = ('<a href="/ask-master/index.php?service=1" '
                  'style="font-weight:bold;color:#14583a">' + label + '</a>')
        after = before.replace('?service=1"', '?service=1&amp;topic=' + topic + '"')
        if result.count(before) != 1:
            raise RuntimeError('OFFER_TOPIC_CHANGED_OFFER_CARD:' + topic)
        result = result.replace(before, after, 1)
    anchor = '<!-- zm-specialist-intent-20261106:services -->'
    if result.count(anchor) != 1:
        raise RuntimeError('OFFER_TOPIC_CHANGED_SERVICE_MARKER')
    result = result.replace(anchor, '<!-- ' + MARKER + ':services -->' + anchor, 1)
    if result.count(MARKER) != 1:
        raise RuntimeError('OFFER_TOPIC_INVALID_SERVICE_PATCH')
    return result


def lint_php(updated: bytes) -> None:
    candidates = [shutil.which('php')]
    candidates.extend(sorted(Path('/opt/cpanel').glob('ea-php*/root/usr/bin/php'), reverse=True))
    binary = next((str(p) for p in candidates if p and Path(p).is_file() and os.access(p, os.X_OK)), None)
    if binary is None:
        raise RuntimeError('OFFER_TOPIC_PHP_LINT_UNAVAILABLE')
    fd, temporary = tempfile.mkstemp(prefix='zm-service-topic-', suffix='.php')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(updated)
        os.chmod(temporary, 0o600)
        result = subprocess.run([binary, '-l', temporary], capture_output=True, timeout=25, check=False)
        if result.returncode != 0:
            raise RuntimeError('OFFER_TOPIC_PHP_LINT_FAILED:' + result.stderr.decode('utf-8','replace')[:250])
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('OFFER_TOPIC_PHP_LINT_OK=1')


def snapshot() -> dict:
    validate()
    rows = {}
    for key, path in FILES.items():
        original = path.read_bytes()
        if sha(original) != EXPECTED[key]:
            raise RuntimeError('OFFER_TOPIC_REFUSE_DIFFERENT_LIVE_VERSION:' + key)
        updated_text = (transform_form if key == 'form' else transform_services)(original.decode('utf-8'))
        updated = updated_text.encode('utf-8')
        rows[key] = {'path': path, 'old': original, 'new': updated,
                     'old_sha': sha(original), 'new_sha': sha(updated),
                     'mode': stat.S_IMODE(path.stat().st_mode)}
    lint_php(rows['form']['new'])
    return rows


def atomic(path: Path, payload: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix='.zm-offer-topic-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def folder(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('OFFER_TOPIC_BAD_RUN_ID')
    return BACKUPS / run_id


def preview() -> None:
    rows = snapshot()
    for key, row in rows.items():
        print('OFFER_TOPIC_PREFLIGHT=' + key + ':' + row['old_sha'] + ':' + row['new_sha'])


def rollback(run_id: str) -> None:
    validate()
    root = folder(run_id)
    manifest = json.loads((root / 'manifest.json').read_text())
    restored = 0
    for key, path in FILES.items():
        item = manifest[key]
        previous = (root / (key + '.backup')).read_bytes()
        if sha(previous) != item['old_sha']:
            raise RuntimeError('OFFER_TOPIC_CORRUPT_BACKUP:' + key)
        current = sha(path.read_bytes())
        if current == item['old_sha']:
            continue
        if current != item['new_sha']:
            raise RuntimeError('OFFER_TOPIC_REFUSE_ROLLBACK_CONCURRENT_CHANGE:' + key)
        atomic(path, previous, item['mode'])
        restored += 1
    print('OFFER_TOPIC_RESTORED=' + str(restored))


def publish(run_id: str) -> None:
    rows = snapshot()
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    root = folder(run_id)
    root.mkdir(mode=0o700)
    manifest = {}
    for key, row in rows.items():
        backup = root / (key + '.backup')
        with backup.open('xb') as f:
            f.write(row['old'])
        backup.chmod(0o600)
        manifest[key] = {name: row[name] for name in ('old_sha','new_sha','mode')}
    (root / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (root / 'manifest.json').chmod(0o600)
    try:
        for key, row in rows.items():
            if row['path'].is_symlink() or sha(row['path'].read_bytes()) != row['old_sha']:
                raise RuntimeError('OFFER_TOPIC_CONCURRENT_CHANGE:' + key)
            atomic(row['path'], row['new'], row['mode'])
            print('OFFER_TOPIC_PUBLISHED=' + key)
    except Exception:
        rollback(run_id)
        raise


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((folder(run_id) / 'manifest.json').read_text())
    for key, path in FILES.items():
        raw = path.read_bytes()
        if sha(raw) != manifest[key]['new_sha']:
            raise RuntimeError('OFFER_TOPIC_ORIGIN_SHA_MISMATCH:' + key)
        if key == 'form':
            if raw.count(MARKER.encode()) != 2:
                raise RuntimeError('OFFER_TOPIC_ORIGIN_FORM_MARKERS_MISSING')
            lint_php(raw)
        else:
            if raw.count(MARKER.encode()) != 1:
                raise RuntimeError('OFFER_TOPIC_ORIGIN_SERVICES_MARKER_MISSING')
        print('OFFER_TOPIC_ORIGIN_VERIFIED=' + key)


def selftest() -> None:
    fake_form = ('zm-ask-master-service-kind-20261106:route '
                 'zm-specialist-intent-20261106:form '
                 "$_POST['kind']='question'; " + POST_OLD + ' ' + FORM_OLD)
    p = transform_form(fake_form)
    assert p.count(MARKER) == 2 and POST_OLD not in p
    assert 'ENT_QUOTES' in p and 'name="service_topic"' in p
    sample = ('zm-services-first-screen-20261106 '
              'zm-service-deliverables-20261106 zm-service-deliverables-20261106 '
              '<!-- zm-specialist-intent-20261106:services --> '
              + ' '.join('<a href="/ask-master/index.php?service=1" style="font-weight:bold;color:#14583a">'
                         + name + '</a>' for name, _ in OFFERS))
    out = transform_services(sample)
    for _, key in OFFERS:
        assert '&amp;topic=' + key in out
    assert out.count(MARKER) == 1
    print('OFFER_TOPIC_SELFTEST_OK=1')


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv == ['selftest']:
        selftest()
    elif argv == ['preview']:
        preview()
    elif len(argv) == 2 and argv[0] in ('publish', 'verify', 'rollback'):
        {'publish': publish, 'verify': verify, 'rollback': rollback}[argv[0]](argv[1])
    else:
        raise RuntimeError('OFFER_TOPIC_UNSAFE_MODE')

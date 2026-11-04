#!/usr/bin/env python3
"""Fail-closed, exact-hash PHP extension deployment on the real cPanel host.

Use in a single authenticated release session. Reads the LIVE PHP app and only
adds small guarded hooks. Never replaces it with the older repository app.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone


BASE = Path('/home/zomorod2/.private/zomorod-business')
APP = BASE / 'app.php'
MODULE = BASE / 'private_auction.php'
STAGED_APP = BASE / '.private_auction_app_stage_20261104.php'
STAGED_MODULE = BASE / '.private_auction_module_stage_20261104.php'
BACKUP = Path('/home/zomorod2/.backups/zomorod-business-20261104-b8dc5cc98583/php/app.php')
EXPECTED_APP_SHA = '2ed9274affa87f3e9c51f7dff0c72d7461118c7aca0ae0ab732b1c81cbfd6005'
RECEIPT = BASE / '.private_auction_release_20261104.receipt'


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def fail(message: str) -> None:
    raise RuntimeError(message)


def assert_backup() -> bytes:
    if not regular_file(BACKUP):
        fail('VERIFIED_PRIVATE_ROLLBACK_BACKUP_MISSING')
    backup_bytes = BACKUP.read_bytes()
    if sha_bytes(backup_bytes) != EXPECTED_APP_SHA:
        fail('VERIFIED_PRIVATE_ROLLBACK_BACKUP_MISMATCH')
    return backup_bytes


def replace_once(data: str, before: str, after: str, label: str) -> str:
    count = data.count(before)
    if count != 1:
        fail('PATCH_ANCHOR_' + label + '_NOT_UNIQUE_' + str(count))
    return data.replace(before, after, 1)


def prepare(module_sha: str) -> None:
    assert_backup()
    if not regular_file(APP) or sha_bytes(APP.read_bytes()) != EXPECTED_APP_SHA:
        fail('LIVE_APP_CHANGED_REQUIRES_NEW_REVIEW')
    if MODULE.exists() or MODULE.is_symlink():
        fail('MODULE_TARGET_ALREADY_EXISTS_STOP')
    if not regular_file(STAGED_MODULE) or sha_bytes(STAGED_MODULE.read_bytes()) != module_sha:
        fail('STAGED_MODULE_MISMATCH')
    source = APP.read_text(encoding='utf-8')
    source = replace_once(
        source,
        'function esc(mixed $s): string {',
        "if (is_file($private.'/private_auction.php')) require_once $private.'/private_auction.php';\n"
        'function esc(mixed $s): string {',
        'PRIVATE_IMPORT',
    )
    source = replace_once(
        source,
        "'users'=>'کاربران'",
        "'private_auction'=>'مزایدهٔ خصوصی','users'=>'کاربران'",
        'NAVIGATION',
    )
    source = replace_once(
        source,
        "$action=req('action');",
        "$action=req('action');\n"
        "        if(str_starts_with($action,'zm_auction_')){\n"
        "            if(!function_exists('zmAuctionHandle')) bail('ماژول مزایده در دسترس نیست.',503);\n"
        "            zmAuctionHandle($db,$action);\n"
        "            $_SESSION['flash']='اقدام مزایده با ثبت ردپا انجام شد.';\n"
        "            header('Location: ?page=private_auction',true,303);exit;\n"
        "        }",
        'POST_ROUTER',
    )
    source = replace_once(
        source,
        "} elseif($page==='accounts'){",
        "} elseif($page==='private_auction'){\n"
        "        if(!function_exists('zmAuctionRender')) bail('ماژول مزایده در دسترس نیست.',503);\n"
        "        zmAuctionRender($db);\n"
        "    } elseif($page==='accounts'){",
        'VIEW_ROUTER',
    )
    output = source.encode('utf-8')
    if len(output) > len(APP.read_bytes()) + 3000 or len(output) < len(APP.read_bytes()):
        fail('PATCH_SIZE_UNEXPECTED')
    if STAGED_APP.is_symlink():
        fail('STAGED_APP_SYMLINK_DENIED')
    with STAGED_APP.open('xb') as stream:
        stream.write(output)
    os.chmod(STAGED_APP, 0o600)
    print('PATCH_PREPARED_ON_EXACT_LIVE_CODE=YES')
    print('PATCH_STAGE_SHA256=' + sha_bytes(output))


def activate(module_sha: str) -> None:
    assert_backup()
    if not regular_file(APP) or sha_bytes(APP.read_bytes()) != EXPECTED_APP_SHA:
        fail('LIVE_APP_CHANGED_BEFORE_ACTIVATION')
    if MODULE.exists() or MODULE.is_symlink():
        fail('MODULE_TARGET_UNEXPECTEDLY_EXISTS')
    if not regular_file(STAGED_APP) or not regular_file(STAGED_MODULE):
        fail('RELEASE_STAGED_FILES_MISSING')
    if sha_bytes(STAGED_MODULE.read_bytes()) != module_sha:
        fail('STAGED_MODULE_CHANGED')
    staged_content = STAGED_APP.read_text(encoding='utf-8')
    if "private_auction.php" not in staged_content or 'zmAuctionRender($db)' not in staged_content:
        fail('PATCH_CONTENT_MISSING')
    expected_staged_sha = sha_bytes(STAGED_APP.read_bytes())
    # The module is installed first but remains unreachable until the app switches.
    os.replace(STAGED_MODULE, MODULE)
    os.chmod(MODULE, 0o600)
    try:
        os.replace(STAGED_APP, APP)
    except Exception:
        # Inert private module remains available for a safe, idempotent review.
        raise
    os.chmod(APP, 0o600)
    with RECEIPT.open('x', encoding='utf-8') as stream:
        stream.write('deployed_utc=' + datetime.now(timezone.utc).isoformat() + '\n')
        stream.write('previous_app_sha256=' + EXPECTED_APP_SHA + '\n')
        stream.write('effective_app_sha256=' + expected_staged_sha + '\n')
        stream.write('module_sha256=' + module_sha + '\n')
        stream.write('backup_path=' + str(BACKUP) + '\n')
    os.chmod(RECEIPT, 0o600)
    print('LIVE_PRIVATE_AUCTION_MODULE_DEPLOYED=YES')
    print('LIVE_APP_SHA256=' + expected_staged_sha)


def rollback() -> None:
    source = assert_backup()
    if not regular_file(APP):
        fail('ROLLBACK_LIVE_APP_MISSING')
    if not regular_file(RECEIPT):
        fail('ROLLBACK_RECEIPT_MISSING')
    lines = RECEIPT.read_text('utf-8').splitlines()
    expected = next((s.split('=', 1)[1] for s in lines if s.startswith('effective_app_sha256=')), None)
    if expected is None or sha_bytes(APP.read_bytes()) != expected:
        fail('ROLLBACK_REFUSED_UNRECOGNIZED_LIVE_APP')
    restored = BASE / '.private_auction_rollback_20261104.php'
    if restored.exists() or restored.is_symlink():
        fail('ROLLBACK_TEMP_ALREADY_EXISTS')
    with restored.open('xb') as stream:
        stream.write(source)
    os.chmod(restored, 0o600)
    os.replace(restored, APP)
    print('ORIGINAL_LIVE_APP_ROLLBACK=COMPLETED')


def main() -> None:
    if len(sys.argv) < 2:
        fail('EXPECTED_PREPARE_ACTIVATE_OR_ROLLBACK')
    mode = sys.argv[1]
    if mode == 'prepare' and len(sys.argv) == 3:
        prepare(sys.argv[2])
    elif mode == 'activate' and len(sys.argv) == 3:
        activate(sys.argv[2])
    elif mode == 'rollback' and len(sys.argv) == 2:
        rollback()
    else:
        fail('INVALID_ARGUMENTS')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('GUARDED_RELEASE_ERROR=' + str(exc), file=sys.stderr)
        sys.exit(1)

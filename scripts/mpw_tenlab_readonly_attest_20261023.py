#!/usr/bin/env python3
"""Read-only attestation for exact installed MojPlayWin five-games/five-tools release.

Does not open or modify a payment route, existing game, other site, or static asset.
No deletes, renames, chmod, or overwrites, including on failure.
"""
from pathlib import Path
import hashlib,json
BASE=Path('/home/zomorod2')
ROOT=BASE/'mojplaywin.com'
ROUTE=ROOT/'game-releases/20261023'
RUN='39908938888'
COMMIT='a3c763bd19343c34a0d2f1a9ae5f08e64a4f4361'
META=BASE/('.mpw-tenlab-stage-'+RUN)/'deploy.json'
GAMES=['windward-regatta','lexicon-sprint','grid-dominion','metro-vault','cargo-switchyard']
TOOLS=['invoice-craft','csv-workbench','image-slimmer','schema-builder','contrast-studio']
def require(ok,msg):
    if not ok:raise RuntimeError('TENLAB_READONLY_REJECT: '+msg)
def sha(p):
    require(p.is_file() and not p.is_symlink(),'not ordinary file '+str(p))
    return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
    require(ROOT.is_dir() and not ROOT.is_symlink(),'root missing')
    require(ROUTE.is_dir() and not ROUTE.is_symlink(),'installed route absent')
    require(META.is_file() and not META.is_symlink(),'private release receipt absent')
    receipt=json.loads(META.read_text('utf8'))
    require(receipt.get('commit')==COMMIT and receipt.get('phase')=='published','wrong release ID / phase')
    hashes=receipt.get('hashes',{})
    expected=set(hashes)|{'hashes.json'}
    actual={str(p.relative_to(ROUTE)) for p in ROUTE.rglob('*') if p.is_file()}
    require(expected==actual,'extra or missing asset '+str(sorted(actual.symmetric_difference(expected))))
    for name,expected_sha in hashes.items():
        require(sha(ROUTE/name)==expected_sha,'file digest mismatch '+name)
    inventory=json.loads((ROUTE/'hashes.json').read_text('utf8'))
    require(inventory=={k:v for k,v in hashes.items() if k!='.htaccess'},'source inventory mismatch')
    require((ROUTE/'.htaccess').read_bytes()==b'PassengerEnabled off\nDirectoryIndex index.html\n','wrong passenger isolation')
    catalogue=json.loads((ROUTE/'release.json').read_text('utf8'))
    require([x['slug'] for x in catalogue['games']]==GAMES and [x['slug'] for x in catalogue['tools']]==TOOLS,'wrong catalogue')
    require(len(list(ROUTE.rglob('index.html')))==11,'wrong page count')
    for slug in GAMES+TOOLS:
        body=(ROUTE/slug/'index.html').read_bytes()
        require(b'<html lang="en">' in body and b'MojPlayWin' in body,'incorrect page language '+slug)
    for name,old_sha in receipt['protected'].items():
        require(sha(ROOT/name)==old_sha,'existing protected site file changed: '+name)
    print('MPW_TENLAB_INSTALLED_BYTES_ATTESTED=PASS')
    print('MPW_TENLAB_FIVE_ENGLISH_GAMES=PASS')
    print('MPW_TENLAB_FIVE_FUNCTIONAL_TOOLS=PASS')
    print('MPW_TENLAB_EXISTING_PASSENGER_AND_STATIC_UNCHANGED=PASS')
    print('MPW_TENLAB_ARTIFACT_FILES='+str(len(actual)))
if __name__=='__main__':verify()

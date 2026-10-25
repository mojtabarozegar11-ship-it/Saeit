#!/usr/bin/env python3
"""Install or roll back only the MojPlayWin Studio Raham route."""
import ast, json, os, pwd, re, shutil, sys, tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
DOCROOT = HOME / 'mojplaywin.com'
APP = HOME / 'Saeit-staging'
BACKUPS = HOME / '.mojplaywin-backups'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_raha_patch import patch_urls, patch_views

APP_FILES = (Path('config/urls.py'), Path('core/views.py'), Path('templates/studio_raha/index.html'))
DOCROOT_FILES = (Path('docroot/studio.Roham/index.html'), Path('docroot/studio.Roham/.htaccess'))
FILES = APP_FILES + DOCROOT_FILES
PUBLIC_HTACCESS = 'PassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n'


def target_for(rel):
    if rel.parts[0] == 'docroot':
        return DOCROOT.joinpath(*rel.parts[1:])
    return APP / rel


def run_id(value):
    if not re.fullmatch(r'[0-9]{1,20}', value):
        raise ValueError('Invalid deployment run id')
    return value


def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix=f'.{path.name}.studio-raha-', delete=False) as f:
        tmp = Path(f.name)
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def restart():
    p = APP / 'tmp/restart.txt'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()


def rollback(value):
    value = run_id(value)
    backup = BACKUPS / f'studio-raha-{value}'
    mf = backup / 'manifest.json'
    if not mf.is_file():
        print('NO_STUDIO_RAHAM_BACKUP')
        return
    manifest = json.loads(mf.read_text())
    for rel in FILES:
        target = target_for(rel)
        item = manifest[str(rel)]
        saved = backup / rel
        if item['existed']:
            if not saved.is_file():
                raise RuntimeError(f'Missing backup for {rel}')
            atomic_write(target, saved.read_text(encoding='utf-8'), item['mode'])
        elif target.exists():
            if target.is_symlink() or not target.is_file():
                raise RuntimeError(f'Refusing to remove unexpected path: {target}')
            target.unlink()
    public_dir = DOCROOT / 'studio.Roham'
    if public_dir.is_dir() and not public_dir.is_symlink():
        try:
            public_dir.rmdir()
        except OSError:
            pass
    restart()
    (backup / 'ROLLED_BACK').write_text('yes\n')
    print('STUDIO_RAHAM_ROLLBACK_COMPLETE')



def verify_public_route(public_dir):
    """Allow only a known, regular Studio Raham installation to be upgraded."""
    if public_dir.is_symlink():
        raise RuntimeError("Refusing symlinked Studio Raham public path")
    if not public_dir.exists():
        return
    if not public_dir.is_dir():
        raise RuntimeError("Studio Raham public path is not a directory")
    index = public_dir / "index.html"
    htaccess = public_dir / ".htaccess"
    if any(path.is_symlink() or not path.is_file() for path in (index, htaccess)):
        raise RuntimeError("Studio Raham existing route is missing protected regular files")
    html = index.read_text(encoding="utf-8")
    if (
        "<title>Studio Raham" not in html
        or 'href="https://mojplaywin.com/studio.Roham/"' not in html
        or 'name="studio-raha-catalog" content="20 games, 20 digital products"' not in html
    ):
        raise RuntimeError("Refusing to overwrite an unrecognized public game route")
    if htaccess.read_text(encoding="utf-8") != PUBLIC_HTACCESS:
        raise RuntimeError("Refusing to change an unknown Studio Raham .htaccess")

def deploy(value, sha):
    value = run_id(value)
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid commit SHA')
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise RuntimeError('Unexpected cPanel account')
    if DOCROOT.is_symlink() or not DOCROOT.is_dir() or APP.is_symlink() or not APP.is_dir():
        raise RuntimeError('MojPlayWin target or Saeit staging app is unsafe')
    if any(not (DOCROOT / x).is_file() for x in ('passenger_wsgi.py', '.htaccess')):
        raise RuntimeError('MojPlayWin Passenger files are missing')
    if 'Saeit-staging' not in (DOCROOT / 'passenger_wsgi.py').read_text(encoding='utf-8', errors='replace'):
        raise RuntimeError('Passenger no longer points at the verified Saeit staging app')
    public_dir = DOCROOT / 'studio.Roham'
    verify_public_route(public_dir)
    stage = HOME / f'.mojplaywin-studio-raha-{value}'
    source = stage / APP_FILES[2]
    if not source.is_file():
        raise RuntimeError('Staged Studio Raham page is missing')
    html = source.read_text(encoding='utf-8')
    if '<title>Studio Raham' not in html or 'https://mojplaywin.com/studio.Roham/' not in html or '20 games, 20 digital products' not in html:
        raise RuntimeError('Studio Raham page metadata validation failed')
    if 'href="/styles.css"' in html or 'src="/app.js"' in html:
        raise RuntimeError('Page contains unresolved root-relative assets')

    targets = [target_for(rel) for rel in FILES]
    if any(p.is_symlink() for p in targets):
        raise RuntimeError('Refusing to replace a symlinked application file')
    updated = {
        APP_FILES[0]: patch_urls(targets[0].read_text(encoding='utf-8')),
        APP_FILES[1]: patch_views(targets[1].read_text(encoding='utf-8')),
        APP_FILES[2]: html,
        DOCROOT_FILES[0]: html,
        DOCROOT_FILES[1]: PUBLIC_HTACCESS,
    }
    ast.parse(updated[APP_FILES[0]])
    ast.parse(updated[APP_FILES[1]])
    backup = BACKUPS / f'studio-raha-{value}'
    if backup.exists():
        raise RuntimeError('Backup already exists')
    backup.mkdir(mode=0o700, parents=True)
    manifest = {}
    for rel, target in zip(FILES, targets):
        existed = target.is_file()
        mode = (target.stat().st_mode & 0o777) if existed else 0o644
        manifest[str(rel)] = {'existed': existed, 'mode': mode}
        if existed:
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    try:
        for rel, target in zip(FILES, targets):
            atomic_write(target, updated[rel], manifest[str(rel)]['mode'])
        restart()
    except Exception:
        rollback(value)
        raise
    (backup / 'DEPLOYED.json').write_text(json.dumps({'commit': sha, 'run_id': value}), encoding='utf-8')
    print(f'STUDIO_RAHAM_FILES_INSTALLED commit={sha}')
    print(f'STUDIO_RAHAM_BACKUP={backup}')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == 'deploy':
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('Usage: deploy_mojplaywin_studio_raha.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID')


if __name__ == '__main__':
    main()

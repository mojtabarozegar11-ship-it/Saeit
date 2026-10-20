"""Pure Python path policy for private research drafts and backups.

A successful validation does not prove cPanel's DocumentRoot configuration:
operators must place private files outside public_html and verify that the
web server cannot serve their URLs. No directory is created here.
"""
import os
import stat
from pathlib import Path


class PrivateStorageError(ValueError):
    """Path may expose customer, research or backup data."""


PUBLIC_COMPONENTS = frozenset({'public_html', 'htdocs', 'httpdocs', 'wwwroot'})


def validate_private_root(directory, *, project_root=None, static_root=None,
                          media_root=None, public_root=None):
    """Reject public, relative, symlink and overly permissive output locations.

    The storage directory may be created afterwards with mode 0700.
    Parents may be traversable by the app user but the private storage root
    itself must be owner-only if already present.
    """
    raw = os.fspath(directory)
    if not raw or not Path(raw).expanduser().is_absolute():
        raise PrivateStorageError('private_root_must_be_absolute')
    original = Path(raw).expanduser()
    canonical = original.resolve(strict=False)
    if canonical != original:
        raise PrivateStorageError('private_root_must_not_contain_symlink')
    if any(part.lower() in PUBLIC_COMPONENTS for part in canonical.parts):
        raise PrivateStorageError('private_root_inside_public_web_directory')
    for root in (project_root, static_root, media_root, public_root):
        if root is None or str(root).strip() == '':
            continue
        resolved = Path(root).expanduser().resolve(strict=False)
        if canonical == resolved or resolved in canonical.parents:
            raise PrivateStorageError('private_root_overlaps_application_or_web_root')
    if canonical.exists():
        if not canonical.is_dir():
            raise PrivateStorageError('private_root_is_not_directory')
        mode = canonical.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise PrivateStorageError('private_root_not_owner_only')
    else:
        parent = canonical.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
            raise PrivateStorageError('private_root_parent_unavailable')
    return canonical

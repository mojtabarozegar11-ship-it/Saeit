"""Exclusive site editorial pipeline lease on the local cPanel filesystem.

Serializes *all* owner-approved site agents, editorial jobs and autopilot runs.
This is NOT a distributed VPS coordinator, and it never creates/changes a web
root or unlocks publishing permissions. Requires a pre-existing private 0700
folder outside the application; failures are fail-closed.

A process/host crash releases the flock kernel lease. Recovering individual
stale DB tasks remains a separately authorized, explicit operator command.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

PUBLIC_NAMES = frozenset(('public_html', 'htdocs', 'httpdocs', 'wwwroot'))
LOCK_FILENAME = 'editorial-pipeline.lock'


class AgentPipelineLockError(ValueError):
    """Non-sensitive error code safe to show to local operators."""


def _private_directory(environ=None, *, project_root=None):
    env = os.environ if environ is None else environ
    raw = env.get('SAEIT_AGENT_LOCK_DIR', '')
    if not raw:
        raise AgentPipelineLockError('private_agent_lock_directory_not_configured')
    path = Path(raw).expanduser()
    if not path.is_absolute() or '..' in path.parts or any(p.lower() in PUBLIC_NAMES for p in path.parts):
        raise AgentPipelineLockError('agent_lock_directory_not_private')
    # Reject symlinks in the configured path and its parents; no redirects to
    # files in another account, document root or application directory.
    if path.resolve(strict=False) != path:
        raise AgentPipelineLockError('agent_lock_directory_symlink_disallowed')
    app_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    if path == app_root or app_root in path.parents:
        raise AgentPipelineLockError('agent_lock_directory_inside_application')
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise AgentPipelineLockError('private_agent_lock_directory_missing') from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or
            info.st_mode & 0o077):
        raise AgentPipelineLockError('agent_lock_directory_must_be_owner_only')
    return path


def lock_directory_status(environ=None, *, project_root=None):
    """Read-only check. No file creation, DB access, or running-status claim."""
    try:
        _private_directory(environ, project_root=project_root)
    except AgentPipelineLockError as exc:
        return str(exc)
    return 'private_agent_lock_configured'


@contextmanager
def editorial_pipeline_lock(environ=None, *, project_root=None):
    """Hold one OS-wide nonblocking lease until all DB processing has ended."""
    folder = _private_directory(environ, project_root=project_root)
    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        directory_stat = os.fstat(directory_fd)
        if (directory_stat.st_uid != os.geteuid() or
                not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_mode & 0o077):
            raise AgentPipelineLockError('agent_lock_directory_must_be_owner_only')
        file_fd = os.open(LOCK_FILENAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                          0o600, dir_fd=directory_fd)
        file_stat = os.fstat(file_fd)
        if (not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.geteuid() or
                file_stat.st_nlink != 1 or file_stat.st_mode & 0o177):
            raise AgentPipelineLockError('agent_lock_file_unsafe')
        try:
            fcntl.flock(file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AgentPipelineLockError('editorial_pipeline_already_running') from exc
    except OSError as exc:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
        raise AgentPipelineLockError('agent_lock_filesystem_unavailable') from exc
    except Exception:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
        raise
    try:
        # Do not mask application/DB errors as lock failures.
        yield
    finally:
        if file_fd is not None:
            # Closing fd also unlocks on crash; never delete the lock inode.
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)

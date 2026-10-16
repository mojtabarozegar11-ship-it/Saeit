import fcntl
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

_app_root = Path(__file__).resolve().parent
_tmp_dir = _app_root / "tmp"
_tmp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
_startup_lock = _tmp_dir / "django-wsgi-startup.lock"

with _startup_lock.open("a", encoding="utf-8") as _lock_file:
    fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX)
    application = get_wsgi_application()

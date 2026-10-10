#!/usr/bin/env python3
"""Install only the staff command center into an existing Django Passenger app.
Preserves all unrelated live files; restores originals if validation fails.
Usage: python3 scripts/activate_staff_panel.py RELEASE_DIR LIVE_DIR
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

release, live = map(lambda x: Path(x).resolve(), sys.argv[1:3])
assert live == Path("/home/zomorod2/Saeit"), "Unexpected production root"
assert (release / "command_center/urls.py").is_file()
assert (live / "manage.py").is_file()
assert (live / ".venv/bin/python").is_file()
assert not (live / "command_center").exists(), "Existing command_center needs manual reconciliation"

urls = live / "config/urls.py"
settings = live / "config/settings.py"
old_urls = urls.read_text()
old_settings = settings.read_text()
assert "staff/" not in old_urls, "Existing staff route requires reconciliation"
assert "command_center" not in old_settings, "Existing app registration requires reconciliation"
# Append independent integration blocks: preserve arbitrary live URL/app layouts.
# Syntax-check originals before writing anything; do not depend on list formatting.
ast.parse(old_urls)
ast.parse(old_settings)
new_urls = old_urls.rstrip() + """

# Staff command center integration (managed by guarded release).
from django.urls import path as staff_path, include as staff_include
from command_center.views import dashboard as staff_dashboard
urlpatterns = [
    staff_path("staff/command-center/", staff_include("command_center.urls")),
    staff_path("staff/", staff_dashboard, name="staff_management"),
] + list(urlpatterns)
"""
new_settings = old_settings.rstrip() + """

# Staff command center integration (managed by guarded release).
INSTALLED_APPS = [*INSTALLED_APPS, "command_center"]
"""
ast.parse(new_urls)
ast.parse(new_settings)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = live.parent / "Saeit-staging" / "backups" / ("staff-" + stamp)
backup.mkdir(parents=True, exist_ok=False)
for rel in ("config/urls.py", "config/settings.py"):
    target = backup / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live / rel, target)
print("BACKUP=" + str(backup), flush=True)

def atomic_write(path, value):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".staff-")
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, "w") as f:
            f.write(value)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

try:
    shutil.copytree(release / "command_center", live / "command_center", symlinks=False)
    atomic_write(urls, new_urls)
    atomic_write(settings, new_settings)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    python = str(live / ".venv/bin/python")
    subprocess.run([python, str(live / "manage.py"), "check"], cwd=live, env=env, check=True, timeout=90)
    subprocess.run([python, "-c", "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import django; django.setup(); from django.urls import reverse; assert reverse('staff_management') == '/staff/'; print('STAFF_ROUTE_OK')"], cwd=live, env=env, check=True, timeout=30)
except BaseException:
    shutil.copy2(backup / "config/urls.py", urls)
    shutil.copy2(backup / "config/settings.py", settings)
    shutil.rmtree(live / "command_center", ignore_errors=True)
    print("ROLLBACK_COMPLETE", flush=True)
    raise
restart = live / "tmp/restart.txt"
restart.parent.mkdir(parents=True, exist_ok=True)
restart.touch()
print("STAFF_ACTIVATED; PASSENGER_RESTART_REQUESTED", flush=True)

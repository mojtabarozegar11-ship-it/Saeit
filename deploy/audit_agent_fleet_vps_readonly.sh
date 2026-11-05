#!/usr/bin/env bash
# Read-only live VPS agent inventory. Does not change cron, code, or database.
set -euo pipefail
umask 077

test "$(id -un)" = githubops || { echo AGENT_AUDIT_WRONG_USER; exit 2; }
base="$HOME/factory-runtime"
app="$base/django-app"
python_bin="$base/.venv/bin/python"
test -x "$python_bin" && test -f "$app/manage.py" || {
  echo AGENT_AUDIT_RUNTIME_NOT_FOUND; exit 2;
}
command -v crontab >/dev/null && command -v ps >/dev/null || {
  echo AGENT_AUDIT_TOOLS_MISSING; exit 2;
}

export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$app"

echo AGENT_FLEET_DATABASE_PREVIEW_BEGIN
"$python_bin" manage.py consolidate_legacy_agents | "$python_bin" -c '
import json, sys
p = json.load(sys.stdin)
assert p["mode"] == "preview"
allowed = {"code", "active", "decision", "active_tasks", "recent_completed_tasks", "recent_publications", "pending_stories", "pending_distributions", "unique_active_capabilities", "review_only_prefix"}
agents = [{k: x[k] for k in allowed if k in x} for x in p["agents"]]
print("AGENT_FLEET_DATABASE_PREVIEW=" + json.dumps({"summary": p["summary"], "agents": agents}, sort_keys=True, separators=(",", ":")))
'

# Never print crontab commands, inline environment values, or process arguments.
"$python_bin" - <<'PY'
import hashlib
import json
import re
import subprocess

cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=12)
if cron.returncode not in (0, 1):
    raise RuntimeError("AGENT_FLEET_CRON_UNREADABLE")
entries = []
for line in cron.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("@") or "=" in line.split()[0]:
        continue
    parts = line.split(maxsplit=5)
    if len(parts) != 6:
        continue
    schedule, command = " ".join(parts[:5]), parts[5]
    # A stable command fingerprint permits duplicates to be located without
    # disclosing URLs, inline secrets, personal paths or command arguments.
    markers = re.findall(r"#\s*([A-Z][A-Z0-9_-]{5,})\s*$", command)
    entries.append({"schedule": schedule, "marker": markers[-1] if markers else None,
                    "command_sha256": hashlib.sha256(command.encode()).hexdigest()[:16]})
print("AGENT_FLEET_USER_CRON=" + json.dumps({"readable": cron.returncode == 0,
    "entries": entries}, sort_keys=True, separators=(",", ":")))

ps = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True, timeout=12, check=True)
needles = ("autonomous_master_loop", "online_income_cycle", "factory", "newsletter", "mojtrade", "mpw_")
counts = {name: 0 for name in needles}
for command in ps.stdout.splitlines():
    # Keep only counts; no process arguments leave the VPS.
    for name in needles:
        if name in command:
            counts[name] += 1
print("AGENT_FLEET_PROCESS_MATCH_COUNTS=" + json.dumps(counts, sort_keys=True, separators=(",", ":")))
PY
echo AGENT_FLEET_AUDIT_READ_ONLY_COMPLETE

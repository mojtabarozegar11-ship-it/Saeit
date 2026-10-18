"""Bounded, source-pinned READ-ONLY dry-run of existing V91 site agent queue."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path("/home/zomorod2/saeit_v91/zomorodmelal")
COMMAND=ROOT/"portal/management/commands/run_site_agents.py"
PY=Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python")
status={"kind":"V91_SITE_AGENT_QUEUE_DRY_RUN","command":"run_site_agents --dry-run --limit 1",
        "permission":"explicitly_off","live_data_modified":False,"publication":False}
if (not ROOT.is_dir() or ROOT.is_symlink() or not COMMAND.is_file()
    or COMMAND.is_symlink() or not PY.exists()):
    status["result"]="missing_or_untrusted_source"
else:
    digest=hashlib.sha256(COMMAND.read_bytes()).hexdigest()
    status["command_pin_prefix"]=digest[:16]
    if not digest.startswith("b9d3c2ab515bbf31"):
        status["result"]="source_changed_refuse_to_run"
    else:
        env={k:v for k,v in os.environ.items() if k not in (
                "DJANGO_SETTINGS_MODULE","DATABASE_URL",
                "SAEIT_SITE_AGENTS_OWNER_ENABLED","SAEIT_AUTOPILOT_OWNER_ENABLED")}
        env["SAEIT_SITE_AGENTS_OWNER_ENABLED"]="0"
        env["SAEIT_AUTOPILOT_OWNER_ENABLED"]="0"
        env["PYTHONDONTWRITEBYTECODE"]="1"
        try:
            p=subprocess.run([str(PY),"-B",str(ROOT/"manage.py"),"run_site_agents",
                              "--dry-run","--limit","1"],
                             cwd=str(ROOT),env=env,stdin=subprocess.DEVNULL,
                             capture_output=True,text=True,timeout=38)
            status["returncode"]=p.returncode
            status["result"]="dry_run_completed" if p.returncode==0 else "dry_run_failed"
            # No raw exception trace, DB DSN, filesystem or account secrets in logs.
            safe=[line for line in p.stdout.splitlines() if line.startswith("DRY RUN:")]
            status["dry_run_report"]=safe[:1]
            if p.returncode!=0:
                status["error_type"]="process_failure_redacted"
        except subprocess.TimeoutExpired:
            status["result"]="timed_out"
        except (OSError,ValueError) as ex:
            status["result"]="unavailable"
            status["error_type"]=type(ex).__name__
print(json.dumps(status,sort_keys=True))

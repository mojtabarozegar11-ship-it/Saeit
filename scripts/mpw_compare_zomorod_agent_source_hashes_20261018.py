"""Compare source-only Zomorod Django site agent files against checked-in shared sources.

Read-only, safe filenames; do NOT read secrets, .env, databases or media.
No Django import, DB access, network or site process changes.
"""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit")
TARGET_FILES=[
 "core/agent_registry.py",
 "core/economic_master_agent.py",
 "core/knowledge_agent.py",
 "core/knowledge_quality.py",
 "core/company_activity_agent.py",
 "core/weather_agent.py",
 "core/newsletter_engine.py",
 "core/worker_runner.py",
 "core/master_agent_capability_pack.py",
 "core/management/commands/autonomous_master_loop.py",
 "core/management/commands/company_activity_agent_cycle.py",
 "core/management/commands/economic_worker.py",
 "core/management/commands/knowledge_agent_cycle.py",
 "core/management/commands/knowledge_agent_generate.py",
 "core/management/commands/newsletter_daily.py",
 "core/management/commands/newsletter_daily_world.py",
 "core/management/commands/run_economic_worker.py",
 "core/management/commands/weather_agent_cycle.py",
]
out={"kind":"ZOMOROD_DJANGO_SITE_SOURCE_AGENT_AUDIT_READONLY","root_found":ROOT.is_dir(),
"source":[],"extra_named_modules":[],"production_or_db_modified":False}
for rel in TARGET_FILES:
 p=ROOT/rel
 row={"path":rel,"present":p.is_file() and not p.is_symlink()}
 if row["present"]:
  try:
   raw=p.read_bytes()
   if len(raw)>250000: raise ValueError("source_oversize")
   tree=ast.parse(raw.decode("utf8"))
   row.update({"sha256":hashlib.sha256(raw).hexdigest(),"byte_count":len(raw),
               "classes":[n.name for n in tree.body if isinstance(n,ast.ClassDef)][:20],
               "functions":[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))][:30]})
  except Exception as ex:
   row["parse_error"]=type(ex).__name__
 out["source"].append(row)
for path in sorted((ROOT/"core").glob("*agent*.py")):
 if path.is_file() and not path.is_symlink() and path.name not in {Path(p).name for p in TARGET_FILES}:
  out["extra_named_modules"].append(path.name)
print(json.dumps(out,ensure_ascii=False,sort_keys=True))

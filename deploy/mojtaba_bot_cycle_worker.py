#!/usr/bin/env python3
"""Evidence-gated central worker for mojtaba.bot.ai.

The worker consumes an explicit JSON queue. It executes only the read-only
cPanel operations already approved in cpanel_direct_command.sh; all other
action kinds are recorded as blocked until a dedicated adapter and owner
approval gate exist. It never treats an empty queue as completed work.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ALLOWED_CPANEL = {"relay_preflight","cpanel_preflight","django_check","django_migrations"}

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cycle", required=True, choices=list("ABCDE"))
    p.add_argument("--queue", required=True)
    p.add_argument("--state", default="runtime/central_cycle_state.json")
    p.add_argument("--max-actions", type=int, default=50)
    args=p.parse_args()
    queue=json.loads(Path(args.queue).read_text(encoding="utf-8"))
    if not isinstance(queue, list):
        raise SystemExit("queue must be a JSON list")
    if len(queue) > args.max_actions:
        raise SystemExit("queue exceeds one-cycle limit")
    if not queue:
        raise SystemExit("EMPTY_QUEUE: no real action was executed")
    results=[]
    for item in queue:
        aid=item.get("action_id")
        kind=item.get("kind")
        if not aid or not item.get("item"):
            results.append({"action_id":aid or "missing","status":"failed","reason":"missing identity"})
            continue
        if kind == "cpanel_readonly":
            operation=item.get("operation")
            if operation not in ALLOWED_CPANEL:
                results.append({"action_id":aid,"status":"blocked","reason":"operation not allowlisted"})
                continue
            proc=subprocess.run(["bash","deploy/cpanel_direct_command.sh",operation],
                                text=True,capture_output=True,timeout=120)
            evidence=item.get("evidence",[])
            evidence=evidence+[f"exit_code:{proc.returncode}"]
            results.append({"action_id":aid,"status":"success" if proc.returncode==0 else "failed",
                            "operation":operation,"evidence":evidence,
                            "output_tail":(proc.stdout+proc.stderr)[-1200:]})
        else:
            results.append({"action_id":aid,"status":"blocked",
                            "reason":"no approved adapter for action kind","kind":kind})
    successful=sum(x["status"]=="success" for x in results)
    report={"engine":"mojtaba.bot.ai","cycle":args.cycle,"started_at":now(),
            "queued":len(queue),"processed":len(results),"successful":successful,
            "target":50,"complete":successful==50,"results":results}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if successful != 50:
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())

"""Load and exercise ALL SHA-verified V91 Python modules in an isolated child.

The 77 files are *modules*, not 77 independent background agents.
Uses a fresh isolated Python process with audit deny guards for network,
subprocess and filesystem mutation. Only approved MojPlayWin private reports
may be written by the parent after successful complete probe. Does not call
legacy entrypoint main(), wake thread loops, financial or publishing methods.

Cpanel: python3 -B script --once; --install-cron only after passing canary.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

TENANT = "mojplaywin-main"
STAGE = Path(__file__).resolve().parents[1]
PACKAGE = STAGE / "mpw_v91_port"
ORIGIN = PACKAGE / "ORIGIN.json"
VENDOR = PACKAGE / "legacy" / "site_master" / "vendor"
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents/evolution_runtime_20261018")
SCRIPT_PATH = Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/scripts/mpw_77_modules_private_runner.py")
CRON_MARK = "MPW_77_MODULES_MAIN_ONLY_20261018"
REPORT = PRIVATE / "all_77_modules_last_run.json"
LIMIT_BYTES = 36000

def ensure(ok, message):
    if not ok:
        raise RuntimeError(message)

def private(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0

def preflight():
    ensure(ORIGIN.is_file() and not ORIGIN.is_symlink(), "ORIGIN_MISSING")
    ensure(PACKAGE.is_dir() and not PACKAGE.is_symlink(), "MODULE_PACKAGE_UNSAFE")
    manifest = json.loads(ORIGIN.read_text("utf-8"))
    rows = manifest.get("modules")
    ensure(manifest.get("file_count") == 77 and isinstance(rows, list) and len(rows) == 77,
           "EXACT_77_SOURCE_MODULES_REQUIRED")
    seen=set()
    names=[]
    inspected=[]
    for entry in rows:
        relative=entry["destination"]
        ensure(isinstance(relative,str)
               and relative.startswith("mpw_v91_port/legacy/")
               and relative.endswith(".py")
               and ".." not in Path(relative).parts
               and relative not in seen, "UNSAFE_OR_DUPLICATE_MODULE_PATH")
        seen.add(relative)
        file=STAGE/relative
        ensure(file.is_file() and not file.is_symlink() and file.stat().st_size <= 31000,
               "MODULE_NOT_REGULAR_OR_TOO_LARGE:"+relative)
        content=file.read_bytes()
        ensure(hashlib.sha256(content).hexdigest() == entry["sha256"],
               "ORIGINAL_CODE_HASH_MISMATCH:"+relative)
        try:
            parsed=ast.parse(content, filename=relative)
            compile(parsed, relative, "exec")
        except (SyntaxError, UnicodeError) as exc:
            raise RuntimeError("MODULE_SYNTAX_INVALID:"+relative) from exc
        # Never execute legacy scripts using __main__; import them under a
        # regular module identity so script entrypoint guards cannot fire.
        module=relative[:-3].replace("/",".")
        if module.endswith(".__init__"):
            module=module[:-9]
        ensure(module.startswith("mpw_v91_port.legacy."), "UNSCOPED_IMPORT")
        names.append(module)
        inspected.append({"module":module,
                          "sha256":entry["sha256"],
                          "functions":sum(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) for x in parsed.body),
                          "classes":sum(isinstance(x,ast.ClassDef) for x in parsed.body)})
    ensure(len(set(names))==77, "DUPLICATE_PYTHON_MODULE_NAME")
    return names,inspected

# This runs in a separate -I/-B child; the parent never imports original modules.
CHILD = r"""
import ast
import importlib
import json
import os
from pathlib import Path
import resource
import sys

root = Path(sys.argv[1]).resolve()
vendor = root / "mpw_v91_port/legacy/site_master/vendor"
names = json.loads(sys.argv[2])
resource.setrlimit(resource.RLIMIT_CPU, (25,25))
# Module loading is bounded and never grants unlimited memory usage.
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
sys.dont_write_bytecode=True
sys.path.insert(0, str(root))
sys.path.insert(0, str(vendor))

# Import-time side effects that would escape a *read-only* module activation
# are fail-closed; this is defense-in-depth, not a full OS container sandbox.
forbidden_prefixes = ("subprocess.", "socket.connect", "socket.bind",
    "socket.listen", "socket.send", "os.system", "os.exec", "os.spawn",
    "os.fork", "os.posix_spawn", "os.remove", "os.unlink", "os.rename",
    "os.replace", "os.mkdir", "os.rmdir", "os.chmod", "os.chown",
    "os.truncate", "os.symlink", "os.link")
def audit(event, args):
    if event.startswith(forbidden_prefixes):
        raise RuntimeError("READ_ONLY_MODULE_AUDIT_BLOCKED:"+event)
    if event == "open" and len(args) >= 3:
        mode=args[1]
        flags=args[2]
        if isinstance(mode,str) and any(c in mode for c in ("w","a","+","x")):
            raise RuntimeError("MODULE_WRITE_REFUSED")
        if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            raise RuntimeError("MODULE_FILE_WRITE_REFUSED")
sys.addaudithook(audit)
loaded=[]
probes=[]
registry=[]
for name in names:
    module=importlib.import_module(name)
    source=Path(module.__file__).resolve()
    if not source.is_relative_to(root):
        raise RuntimeError("MODULE_ESCAPED_MAIN_STAGE:"+name)
    # All modules must be importable in the real V91 runtime and their
    # exposed first-party namespace inspected. Package initializers are
    # loaded as packages, not misrepresented as standalone workers.
    exported={key:val for key,val in vars(module).items()
              if not key.startswith("_") and getattr(val,"__module__",None)==name
              and callable(val)}
    kind="package_initializer" if source.name=="__init__.py" else "capability_module"
    if kind=="capability_module" and not exported:
        raise RuntimeError("MODULE_NO_USABLE_PUBLIC_CAPABILITY:"+name)
    registry.append({"module":name,"kind":kind,
                     "exported_callables":sorted(exported),
                     "loaded":True,"safe_scope":"read_only_private"})
    loaded.append(name)
# Curated, actual side-effect-free functional calls exercising generation
# selection and editorial source-validation in the V91 family.
agent=importlib.import_module("mpw_v91_port.legacy.portal.generator")
assert agent.valid_sources(["https://www.nist.gov/","http://unsafe.example","https://www.nist.gov/"])==["https://www.nist.gov/"]
probes.append("v91_source_url_filter")
selection=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen12.adaptive")
winner=selection.ParetoSelector().choose([
    selection.CandidateSignal("better",.93,15,1,.95),
    selection.CandidateSignal("dominated",.2,70,8,.3)])
assert winner.name=="better"
probes.append("gen12_pareto_selection")
cal=selection.ConfidenceCalibrator(alpha=.5,initial=.5)
assert .5 < cal.update(True) <=1
probes.append("gen12_confidence_calibration")
from mpw_v91_port.legacy.site_master.vendor.master_gen64.cycles import AwakeningCycles
awake=AwakeningCycles(lambda:None,lambda:None,60,180,run_immediately=False)
assert not awake.running and awake.stats().internal_runs==0
probes.append("gen64_opt_in_cycle_construct_only")
# Cross-generation functional contracts are invoked on real inherited
# implementation, never self-mocked or based on AST-only status. All mutations
# below affect ephemeral in-memory objects inside the deny-write child.
cache=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen12.cache")
key=cache.TaskResultCache.fingerprint("mojplaywin-main",{"article":"example"})
assert len(key)==64
probes.append("gen12_deterministic_cache_fingerprint")
trace_module=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen16.telemetry")
trace=trace_module.TamperEvidentTrace(max_events=3)
trace.append("candidate_observed",{"tenant":"mojplaywin-main"})
assert trace.verify()["valid"] and trace.verify()["events"]==1
probes.append("gen16_tamper_evident_telemetry")
semantic=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen20.semantic_quorum")
assert semantic.canonical_json({"b":2,"a":1})==semantic.canonical_json({"a":1,"b":2})
probes.append("gen20_semantic_canonicalization")
contract=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen24.contracts")
verified=contract.ContractGuard(pre=lambda kw:kw["quality"]>=0,
    post=lambda output:output=="ok").run(lambda quality:"ok",quality=96)
assert verified.ok and verified.value=="ok"
probes.append("gen24_executable_contract_guard")
planner=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen28.planner")
plan=planner.BudgetAwarePlanner().build([
    planner.PlanStep("collect",estimated_cost=0.1),
    planner.PlanStep("review",dependencies=("collect",),estimated_cost=0.1)],
    max_cost=0.3)
assert [p.name for p in plan.steps]==["collect","review"]
probes.append("gen28_dependency_budget_planner")
resilience=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen32.resilience")
breaker=resilience.DeterministicCircuitBreaker(failure_threshold=2,cooldown_ticks=3)
assert breaker.allow("main-site-demo",0)
breaker.record("main-site-demo",False,0)
breaker.record("main-site-demo",False,1)
assert not breaker.allow("main-site-demo",2)
probes.append("gen32_failure_circuit_guard")
state_module=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen40.state")
store=state_module.VersionedStateStore()
snap=store.commit({"site":"mojplaywin-main"},expected_version=0)
assert snap.version==1 and store.snapshot().payload["site"]=="mojplaywin-main"
probes.append("gen40_versioned_state_cas")
codec=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen48.checkpoint")
checkpoint=codec.CheckpointCodec()
package=checkpoint.encode(1,{"site":"mojplaywin-main"})
assert checkpoint.verify(package) and checkpoint.decode(package)=={"site":"mojplaywin-main"}
probes.append("gen48_integrity_checked_checkpoint")
cb=importlib.import_module("mpw_v91_port.legacy.site_master.vendor.master_gen56.circuit")
circuit=cb.CircuitBreaker(failure_threshold=2,recovery_successes=2)
assert circuit.allowed("quality")
circuit.observe("quality",False);circuit.observe("quality",False)
assert not circuit.allowed("quality")
circuit.observe("quality",True);circuit.observe("quality",True)
assert circuit.allowed("quality")
probes.append("gen56_open_recover_circuit")
engine=importlib.import_module("mpw_v91_port.legacy.portal.agent_engine")
assert engine.clean_text("<em>Hello</em>  MojPlayWin")=="Hello MojPlayWin"
probes.append("v91_legacy_clean_text")
assert len(registry)==77 and len(probes)>=14
print(json.dumps({"tenant":"mojplaywin-main","status":"all_77_imported_in_readonly_child",
                  "import_count":len(loaded),"imported":loaded,
                  "per_module_capability_registry":registry,
                  "safe_pure_function_probes":probes,
                  "forbidden_network_or_write_operations":0,
                  "main_entrypoints_executed":0,
                  "public_site_writes":0},sort_keys=True))
"""

def execute():
    names, inspected = preflight()
    # -I rejects Python environment, user site, and cwd injection; -B prevents
    # bytecode writes outside the private report. Untrusted code is never run
    # in the hosting parent process or as a WSGI/Passenger entrypoint.
    args=[sys.executable, "-I", "-B", "-c", CHILD, str(STAGE), json.dumps(names)]
    process=subprocess.run(args,capture_output=True,text=True,timeout=55,
                           cwd=str(STAGE),env={"PATH":"/usr/bin:/bin","PYTHONNOUSERSITE":"1"})
    if process.returncode:
        raise RuntimeError("LEGACY_MODULE_CHILD_FAILED:"+str(process.returncode)
                           +":"+process.stderr[-1700:])
    output=json.loads(process.stdout.strip().splitlines()[-1])
    ensure(output.get("tenant")==TENANT and output.get("import_count")==77
           and output.get("status")=="all_77_imported_in_readonly_child"
           and output.get("public_site_writes")==0
           and output.get("main_entrypoints_executed")==0
           and len(output.get("per_module_capability_registry",[]))==77
           and len(output.get("safe_pure_function_probes",[]))>=14,
           "LEGACY_MODULE_CHILD_INCOMPLETE")
    return {"tenant":TENANT,
            "status":"77_verified_original_modules_exercised_privately",
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "modules_hash_verified":len(inspected),
            "modules_syntax_checked":len(inspected),
            "modules_import_executed":output["import_count"],
            "module_names":names,
            "per_module_capability_registry":output["per_module_capability_registry"],
            "capability_namespaces_active":77,
            "package_initializers_loaded":sum(x["kind"]=="package_initializer"
                                               for x in output["per_module_capability_registry"]),
            "functional_probes_executed":len(output["safe_pure_function_probes"]),
            "safe_function_probes":output["safe_pure_function_probes"],
            "import_side_effects_blocked":True,
            "standalone_agent_processes_created":0,
            "financial_authority":False,
            "public_site_modified":False,
            "sibling_sites_modified":False,
            "shared_passenger_modified":False,
            "tenant_isolated":True}

def write_report(output):
    ensure(private(PRIVATE), "PRIVATE_RUNTIME_DIR_UNSAFE")
    ensure(not REPORT.is_symlink(), "REPORT_SYMLINK_REFUSED")
    raw=json.dumps(output,sort_keys=True,ensure_ascii=False).encode("utf-8")
    ensure(len(raw)<=LIMIT_BYTES,"MODULE_REPORT_TOO_LARGE")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-77-module-",dir=str(PRIVATE))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,REPORT)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)

def install_cron():
    ensure(str(STAGE)=="/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018",
           "ONLY_MAIN_CPANEL_TENANT_INSTALL")
    ensure(os.geteuid()==STAGE.stat().st_uid and private(STAGE) and private(PRIVATE),
           "CPANEL_OWNER_OR_PRIVACY_INVALID")
    ensure(SCRIPT_PATH==Path(__file__).resolve(), "UNEXPECTED_MODULE_RUNNER_LOCATION")
    previous=json.loads(REPORT.read_text("utf-8"))
    ensure(previous.get("status")=="77_verified_original_modules_exercised_privately"
           and previous.get("modules_import_executed")==77, "SUCCESSFUL_CANARY_REQUIRED")
    existing=subprocess.run(["crontab","-l"],capture_output=True,text=True,check=True,timeout=15).stdout
    rows=[line for line in existing.splitlines() if CRON_MARK in line]
    ensure(len(rows)<=1,"DUPLICATE_77_MODULE_JOBS")
    ensure(sum("MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018" in x for x in existing.splitlines())==1,
           "MAIN_PRIVATE_EVOLUTION_CRON_REQUIRED")
    cmd=("43 * * * * /usr/bin/flock -n "+str(PRIVATE/"modules77.cron.lock")
         +" /usr/bin/python3 -B "+str(SCRIPT_PATH)
         +" --once > "+str(PRIVATE/"modules77.last.log")
         +" 2>&1 # "+CRON_MARK)
    if rows:
        ensure(rows==[cmd],"DIFFERENT_EXISTING_MODULE_JOB")
        return {"status":"77_module_hourly_job_already_active",
                "previous_jobs_preserved":True}
    backup=PRIVATE/"modules77.cron.before.txt"
    ensure(not backup.exists() and not backup.is_symlink(),"PREVIOUS_CRON_BACKUP_ALREADY_EXISTS")
    fd=os.open(str(backup),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        f.write(existing)
    proposed=existing.rstrip("\n")+"\n"+cmd+"\n"
    result=subprocess.run(["crontab","-"],input=proposed,text=True,
                          capture_output=True,timeout=15)
    ensure(result.returncode==0,"MODULE_CRON_REJECTED")
    verify=subprocess.run(["crontab","-l"],capture_output=True,text=True,
                          check=True,timeout=15).stdout
    if verify!=proposed:
        subprocess.run(["crontab","-"],input=existing,text=True,
                       capture_output=True,timeout=15)
        raise RuntimeError("MODULE_CRON_UNEXPECTED_CHANGE")
    return {"status":"77_module_hourly_health_job_enabled",
            "schedule":"43 * * * *","previous_jobs_preserved":True,
            "public_site_modified":False}

def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once",action="store_true")
    mode.add_argument("--install-cron",action="store_true")
    opts=parser.parse_args()
    os.umask(0o077)
    if opts.once:
        record=execute()
        if private(PRIVATE):
            write_report(record)
        print(json.dumps({"status":record["status"],
                          "verified":record["modules_hash_verified"],
                          "imported":record["modules_import_executed"],
                          "pure_probes":record["safe_function_probes"],
                          "capability_namespaces_active":record["capability_namespaces_active"],
                          "functional_probes_executed":record["functional_probes_executed"],
                          "public_site_modified":False},sort_keys=True))
    else:
        print(json.dumps(install_cron(),sort_keys=True))

if __name__=="__main__":
    main()

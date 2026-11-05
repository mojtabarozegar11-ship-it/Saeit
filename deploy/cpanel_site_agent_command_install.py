#!/usr/bin/env python3
"""Install two already-existing Django agent commands on the verified cPanel app.

No database changes, task execution, paid API calls or publication. Never
overwrite an existing, divergent command; rollback only files created here.
"""

import argparse
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys


COMMANDS = (
    "company_activity_agent_cycle",
    "knowledge_agent_cycle",
)
REQUIRED_MODELS = (
    ("core.company_activity_models", "CompanyActivityAgentPlan"),
    ("core.company_activity_models", "CompanyActivityReport"),
    ("core.knowledge_agent_models", "KnowledgeAgentPlan"),
    ("core.knowledge_agent_models", "KnowledgeBook"),
    ("core.knowledge_agent_models", "KnowledgeAgentRun"),
    ("core.models", "Agent"),
    ("core.models", "AgentTask"),
    ("core.models", "NewsletterStory"),
)
REQUIRED_FIELDS = {
    "CompanyActivityAgentPlan": {"code", "active", "cadence_hours", "reports_per_day", "require_owner_approval", "next_run_at", "last_run_at"},
    "CompanyActivityReport": {"plan", "report_type", "period_start", "period_end", "source_activity_ids", "source_count", "content", "approval_required", "status"},
    "KnowledgeAgentPlan": {"code", "active", "next_run_at", "last_run_at", "cadence_hours", "require_owner_approval"},
    "KnowledgeBook": {"code", "plan", "status", "generated_sections", "outline"},
    "KnowledgeAgentRun": {"plan", "book", "status", "objective", "approval_required"},
    "Agent": {"code", "name", "mission", "risk_level", "active"},
    "AgentTask": {"agent", "action_type", "capability_code", "risk_snapshot", "input_data", "status"},
    "NewsletterStory": {"company_activity_kind", "company_activity_content", "company_unit_title", "company_project_title", "company_activity_status", "summary", "title"},
}


def require_regular(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("AGENT_COMMAND_UNSAFE_FILE:" + path.name)
    if not stat.S_ISREG(path.stat().st_mode):
        raise RuntimeError("AGENT_COMMAND_NONREGULAR_FILE:" + path.name)


def verify_runtime(app, python):
    os.chdir(app)
    sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection
    from importlib import import_module

    if not (app / "manage.py").is_file():
        raise RuntimeError("AGENT_COMMAND_APP_NOT_FOUND")
    if Path(sys.executable).resolve() != python.resolve():
        raise RuntimeError("AGENT_COMMAND_WRONG_PYTHON")
    with connection.cursor() as cursor:
        available_tables = set(connection.introspection.table_names(cursor))
        for module_name, model_name in REQUIRED_MODELS:
            model = getattr(import_module(module_name), model_name)
            model_fields = {field.name for field in model._meta.get_fields()}
            if not REQUIRED_FIELDS[model_name].issubset(model_fields):
                raise RuntimeError("AGENT_COMMAND_MODEL_FIELDS_MISSING:" + model_name)
            if model._meta.db_table not in available_tables:
                raise RuntimeError("AGENT_COMMAND_REQUIRED_TABLE_MISSING:" + model_name)
            columns = {col.name for col in connection.introspection.get_table_description(cursor, model._meta.db_table)}
            needed = {field.column for field in model._meta.local_concrete_fields}
            if not needed.issubset(columns):
                raise RuntimeError("AGENT_COMMAND_TABLE_COLUMNS_MISSING:" + model_name)
    subprocess.run([str(python), "manage.py", "check"], check=True, cwd=app)
    subprocess.run([str(python), "manage.py", "migrate", "--check"], check=True, cwd=app)


def verify_staged_commands(stage):
    for command in COMMANDS:
        source = stage / "core" / "management" / "commands" / (command + ".py")
        require_regular(source)
        spec = importlib.util.spec_from_file_location("_saeit_stage_" + command, source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "Command"):
            raise RuntimeError("AGENT_COMMAND_CLASS_MISSING:" + command)


def install(app, stage, python, run_id):
    verify_runtime(app, python)
    verify_staged_commands(stage)
    target_dir = app / "core" / "management" / "commands"
    if target_dir.is_symlink() or not target_dir.is_dir():
        raise RuntimeError("AGENT_COMMAND_TARGET_DIRECTORY_UNSAFE")

    to_install = []
    for command in COMMANDS:
        name = command + ".py"
        source = stage / "core" / "management" / "commands" / name
        target = target_dir / name
        if target.exists() or target.is_symlink():
            require_regular(target)
            if source.read_bytes() != target.read_bytes():
                raise RuntimeError("AGENT_COMMAND_EXISTING_DIFFERENT:" + name)
            continue
        to_install.append((source, target))

    inserted = {}
    try:
        for source, target in to_install:
            temp = target.with_name("." + target.name + "." + run_id + ".incoming")
            if temp.exists() or temp.is_symlink():
                raise RuntimeError("AGENT_COMMAND_TEMP_ALREADY_EXISTS")
            fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(source.read_bytes())
                    output.flush()
                    os.fsync(output.fileno())
                os.link(temp, target, follow_symlinks=False)  # atomic, never overwrites
                inserted[target] = target.stat().st_ino
            finally:
                if temp.exists() and not temp.is_symlink():
                    temp.unlink()

        proc = subprocess.run(
            [str(python), "manage.py", "help", "--commands"],
            check=True, capture_output=True, text=True, cwd=app,
        )
        registered = set(proc.stdout.splitlines())
        if not set(COMMANDS).issubset(registered):
            raise RuntimeError("AGENT_COMMAND_NOT_REGISTERED_AFTER_INSTALL")
        subprocess.run([str(python), "manage.py", "check"], check=True, cwd=app)
        print("CPANEL_AGENT_COMMAND_INSTALL=verified")
        print("CPANEL_AGENT_COMMAND_NEW_FILES=" + str(len(inserted)))
        print("CPANEL_AGENT_TASKS_EXECUTED=0")
        print("CPANEL_AGENT_EXTERNAL_MESSAGES_SENT=0")
    except Exception:
        for target, inode in inserted.items():
            if not target.is_symlink() and target.exists() and target.stat().st_ino == inode:
                target.unlink()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    app = Path(args.app)
    stage = Path(args.stage)
    python = Path(args.python)
    if (str(app) != "/home/zomorod2/Saeit" or app.is_symlink()
            or stage.parent != Path("/home/zomorod2/.private")
            or not stage.name.startswith("saeit-agent-cmd-")
            or not args.run_id.isdigit()
            or stage.name != "saeit-agent-cmd-" + args.run_id
            or not stage.is_dir() or stage.is_symlink()):
        raise SystemExit("AGENT_COMMAND_PATH_GUARD_FAILED")
    install(app, stage, python, args.run_id)


if __name__ == "__main__":
    main()

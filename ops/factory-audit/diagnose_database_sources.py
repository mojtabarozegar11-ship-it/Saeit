#!/usr/bin/env python3
"""Read-only cross-source DB audit: live Django ORM vs independent private SQLite.

No prints of DB names, environment secrets, product titles, or customer data.
No changes to Django records, database, cron, websites or factory processes.
"""
import hashlib
import os
from pathlib import Path
import sqlite3

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connections

HOME = Path.home().resolve()
PRIVATE = HOME / "factory-runtime/private/factory-fresh-isolated.sqlite3"
Product = apps.get_model("core", "Product")
Project = apps.get_model("core", "ResearchProject")
Task = apps.get_model("core", "AgentTask")


def category(path):
    try:
        p = Path(path).expanduser().resolve(strict=False)
    except (OSError, ValueError, TypeError):
        return "INVALID"
    for name, root in (
        ("FACTORY_PRIVATE", HOME / "factory-runtime/private"),
        ("FACTORY_DJANGO_SOURCE", HOME / "factory-runtime/django-app"),
        ("FACTORY_OPERATIONS", HOME / "factory-runtime/operations"),
        ("USER_HOME_OTHER", HOME),
    ):
        try:
            p.relative_to(root.resolve())
            return name
        except ValueError:
            pass
    return "OUTSIDE_HOME"


def sqlite_counts(path):
    p = Path(path).expanduser()
    if not p.is_file() or p.is_symlink():
        return {"error":"ABSENT_OR_SYMLINK"}
    conn = sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True,timeout=12)
    try:
        conn.execute("PRAGMA query_only=ON")
        columns={r[1] for r in conn.execute("PRAGMA table_info(core_product)")}
        if not {"id","factory_managed","active","owner_id"}.issubset(columns):
            return {"error":"PRODUCT_SCHEMA_INCOMPATIBLE"}
        result={
            "total":conn.execute("SELECT COUNT(*) FROM core_product").fetchone()[0],
            "drafts":conn.execute("SELECT COUNT(*) FROM core_product WHERE factory_managed=1 AND active=0").fetchone()[0],
            "active":conn.execute("SELECT COUNT(*) FROM core_product WHERE active=1").fetchone()[0],
            "no_owner":conn.execute("SELECT COUNT(*) FROM core_product WHERE factory_managed=1 AND owner_id IS NULL").fetchone()[0],
            "last_id":conn.execute("SELECT MAX(id) FROM core_product").fetchone()[0] or 0,
        }
        ids={r[0] for r in conn.execute(
            "SELECT id FROM core_product WHERE factory_managed=1 AND active=0 LIMIT 10000")}
        result["private_draft_ids"]=ids
        return result
    finally:
        conn.close()


def run():
    d=connections["default"]
    engine=d.settings_dict.get("ENGINE","")
    dbname=d.settings_dict.get("NAME")
    print("FACTORY_ORM_ENGINE_SQLITE="+str(engine.endswith("sqlite3")))
    print("FACTORY_ORM_DB_FILE_CATEGORY="+category(dbname) if engine.endswith("sqlite3") else "FACTORY_ORM_DB_FILE_CATEGORY=NON_SQLITE")
    print("FACTORY_PRIVATE_DB_FILE_CATEGORY="+category(PRIVATE))
    print("FACTORY_ORM_PRODUCT_TOTAL="+str(Product.objects.count()))
    print("FACTORY_ORM_FACTORY_DRAFTS="+str(Product.objects.filter(factory_managed=True,active=False).count()))
    print("FACTORY_ORM_PROJECT_TOTAL="+str(Project.objects.count()))
    print("FACTORY_ORM_BLOCKED_TASKS="+str(Task.objects.filter(status="blocked").count()))
    private=sqlite_counts(PRIVATE)
    if "error" in private:
        print("FACTORY_PRIVATE_DB_ERROR="+private["error"])
        raise RuntimeError("PRIVATE_DB_MISSING_OR_INVALID")
    for k in ("total","drafts","active","no_owner","last_id"):
        print("FACTORY_PRIVATE_DB_"+k.upper()+"="+str(private[k]))
    if engine.endswith("sqlite3"):
        django_db=sqlite_counts(dbname)
        if "error" in django_db:
            print("FACTORY_DJANGO_DIRECT_ERROR="+django_db["error"])
            raise RuntimeError("DJANGO_DB_MISSING_OR_INVALID")
        print("FACTORY_ORM_DB_SAME_PATH_AS_PRIVATE="+str(os.path.samefile(dbname,PRIVATE)))
        for k in ("total","drafts","active","last_id"):
            print("FACTORY_DJANGO_DIRECT_"+k.upper()+"="+str(django_db[k]))
        if django_db["total"] != Product.objects.count():
            print("FACTORY_ORM_DIRECT_MISMATCH")
        print("FACTORY_PRIVATE_VS_ORM_DRAFT_ID_INTERSECTION="+str(
            len(private["private_draft_ids"] & django_db["private_draft_ids"])))
        print("FACTORY_PRIVATE_ONLY_DRAFT_IDS="+str(
            len(private["private_draft_ids"] - django_db["private_draft_ids"])))
    print("FACTORY_DATABASES_NOT_RECONCILED")
    print("FACTORY_DATABASE_IDENTITY_DIAGNOSTIC_COMPLETE")


if __name__ == "__main__":
    run()

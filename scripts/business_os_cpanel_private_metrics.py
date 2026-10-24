"""Make a private, read-only business snapshot *on cPanel only*.

Do not return any observation, count, finding, exception, or filename in stdout,
stderr, SSH output, CI logs, CI artifacts, or GitHub.  The runner receives only
a fixed success/failure marker from its remote command's exit status.
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile


PRODUCTION_ROOT = Path("/home/zomorod2/Saeit")
STAGING_RELEASES = Path("/home/zomorod2/Saeit-staging/releases")
_phase = "paths"


def produce_private_snapshot():
    global _phase
    source_root = Path(__file__).resolve().parent.parent
    # A fixed output location, guaranteed to stay under the intended private
    # cPanel staging hierarchy; never accept an arbitrary output path.
    if STAGING_RELEASES.resolve() not in source_root.parents:
        raise RuntimeError("Invalid release location")
    if not (PRODUCTION_ROOT / "config" / "settings.py").is_file():
        raise RuntimeError("Expected production Django project unavailable")

    sys.path.insert(0, str(PRODUCTION_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    _phase = "django_import"
    import django

    _phase = "django_setup"
    django.setup()
    _phase = "model_import"
    from django.conf import settings
    from django.core.exceptions import FieldError
    from django.utils import timezone
    from django.db import DatabaseError, connections
    from core.models import AgentTask, ApprovalRequest, Order, Product

    # Load reviewed, version-pinned analysis only from the staged release.
    # Do not import/overwrite the installed production 'core' package.
    review_path = source_root / "core" / "business_management.py"
    _phase = "review_load"
    spec = importlib.util.spec_from_file_location("business_os_staged_review", review_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Invalid staged review code")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    captured_at = timezone.now().isoformat()

    def observed(value, table):
        return module.observed(value, f"cpanel_local_django:{table}", captured_at)

    _phase = "db_connect"
    default_db = settings.DATABASES["default"]
    if default_db.get("ENGINE", "").endswith("sqlite3"):
        sqlite_path = Path(str(default_db.get("NAME", "")))
        # SQLite creates a missing DB on connect; prevent even that write.
        if not sqlite_path.is_file():
            raise RuntimeError("No existing read-only SQLite source")
    connections["default"].ensure_connection()

    def missing_source_reason(model, required_columns):
        """Identify schema drift locally; never expose schema in CI logs."""
        try:
            with connections["default"].cursor() as cursor:
                introspection = connections["default"].introspection
                table = model._meta.db_table
                if table not in introspection.table_names(cursor):
                    return "expected_table_missing_in_connected_database"
                present = {field.name for field in introspection.get_table_description(cursor, table)}
                if not set(required_columns).issubset(present):
                    return "expected_columns_missing_in_connected_table"
                return "query_failed_despite_expected_schema"
        except (DatabaseError, FieldError):
            return "schema_introspection_unavailable"

    def safe_count(model, table, required_columns, query):
        # A table not deployed to this database is UNKNOWN, not zero.
        # Continue checking the other independent sources.
        try:
            return observed(query(), table)
        except (DatabaseError, FieldError):
            return module.unknown(
                f"{table}: {missing_source_reason(model, required_columns)}"
            )

    _phase = "queued_tasks_query"
    queued_tasks = safe_count(AgentTask, "AgentTask", ("status",),
                              lambda: AgentTask.objects.filter(status="queued").count())
    _phase = "blocked_tasks_query"
    blocked_tasks = safe_count(AgentTask, "AgentTask", ("status",),
                               lambda: AgentTask.objects.filter(status="blocked").count())
    _phase = "products_query"
    active_products = safe_count(Product, "Product", ("active",),
                                 lambda: Product.objects.filter(active=True).count())
    _phase = "orders_query"
    orders = safe_count(Order, "Order", ("id",), lambda: Order.objects.count())
    _phase = "approvals_query"
    pending_approvals = safe_count(ApprovalRequest, "ApprovalRequest", ("status",),
                                   lambda: ApprovalRequest.objects.filter(status="pending").count())
    metrics = {
        "queued_tasks": queued_tasks,
        "blocked_tasks": blocked_tasks,
        "active_products": active_products,
        "orders": orders,
        "pending_approvals": pending_approvals,
        "independently_validated_market": module.unknown("Independent buyer-demand evidence not attached"),
        "verified_collected_cash": module.unknown("No payment-provider/ledger reconciliation"),
        "accepted_factory_products": module.unknown("VPS production and QA evidence not connected"),
        "site_health": module.unknown("Independent site health sensor not connected"),
    }
    _phase = "review_compute"
    report = module.review_business(metrics)
    report.update({
        "generated_at": captured_at,
        "scope": "local_cpanel_django_only; excludes other stores, VPS and providers",
        "metrics": metrics,
    })

    _phase = "private_write"
    private_dir = source_root / "private"
    private_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private_dir, 0o700)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=private_dir,
            prefix=".business-review-", suffix=".json", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            json.dump(report, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, private_dir / "business-review.json")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        produce_private_snapshot()
    except Exception:
        # Fixed exit codes expose only the technical phase, no exception details.
        raise SystemExit({
            "paths": 71, "django_import": 72, "django_setup": 73,
            "model_import": 74, "review_load": 75,
            "review_compute": 77, "private_write": 78,
            "db_connect": 80, "queued_tasks_query": 81,
            "blocked_tasks_query": 82, "products_query": 83,
            "orders_query": 84, "approvals_query": 85,
        }.get(_phase, 79))
    print("BUSINESS_OS_PRIVATE_REPORT_CREATED")

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


def produce_private_snapshot():
    source_root = Path(__file__).resolve().parent.parent
    # A fixed output location, guaranteed to stay under the intended private
    # cPanel staging hierarchy; never accept an arbitrary output path.
    if STAGING_RELEASES.resolve() not in source_root.parents:
        raise RuntimeError("Invalid release location")
    if not (PRODUCTION_ROOT / "config" / "settings.py").is_file():
        raise RuntimeError("Expected production Django project unavailable")

    sys.path.insert(0, str(PRODUCTION_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.utils import timezone
    from core.models import AgentTask, ApprovalRequest, Order, Product

    # Load reviewed, version-pinned analysis only from the staged release.
    # Do not import/overwrite the installed production 'core' package.
    review_path = source_root / "core" / "business_management.py"
    spec = importlib.util.spec_from_file_location("business_os_staged_review", review_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Invalid staged review code")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    captured_at = timezone.now().isoformat()

    def observed(value, table):
        return module.observed(value, f"cpanel_local_django:{table}", captured_at)

    metrics = {
        "queued_tasks": observed(AgentTask.objects.filter(status="queued").count(), "AgentTask"),
        "blocked_tasks": observed(AgentTask.objects.filter(status="blocked").count(), "AgentTask"),
        "active_products": observed(Product.objects.filter(active=True).count(), "Product"),
        "orders": observed(Order.objects.count(), "Order"),
        "pending_approvals": observed(ApprovalRequest.objects.filter(status="pending").count(), "ApprovalRequest"),
        "independently_validated_market": module.unknown("Independent buyer-demand evidence not attached"),
        "verified_collected_cash": module.unknown("No payment-provider/ledger reconciliation"),
        "accepted_factory_products": module.unknown("VPS production and QA evidence not connected"),
        "site_health": module.unknown("Independent site health sensor not connected"),
    }
    report = module.review_business(metrics)
    report.update({
        "generated_at": captured_at,
        "scope": "local_cpanel_django_only; excludes other stores, VPS and providers",
        "metrics": metrics,
    })

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
        # Intentionally suppress all traceback, business data, paths and counts.
        print("BUSINESS_OS_PRIVATE_PROBE_FAILED", file=sys.stderr)
        raise SystemExit(1)
    print("BUSINESS_OS_PRIVATE_REPORT_CREATED")

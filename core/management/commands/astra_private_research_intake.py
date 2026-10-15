"""Bounded research-only intake of legacy factory drafts into isolated Astra 0049.

No orders required; scans eligible unpublished old-factory records. Cannot
authorize a product build, price, verified demand, publication or payments.
Default is read-only. --apply-private is allowed only for disposable CI SQLite.
"""
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import FactoryQueueItem

MAX_TICK = 100
QUERY = """
SELECT p.id, COUNT(DISTINCT s.id), COUNT(DISTINCT e.id)
FROM core_product AS p
LEFT JOIN core_factoryrun AS run ON run.product_id=p.id
LEFT JOIN core_researchproject AS rp ON rp.factory_run_id=run.id
LEFT JOIN core_researchsource AS s ON s.project_id=rp.id
LEFT JOIN core_evidence AS e ON e.project_id=rp.id AND e.source_id=s.id
WHERE p.factory_managed=1 AND p.active=0 AND p.id>%s
GROUP BY p.id
ORDER BY p.id
LIMIT %s
"""


def _can_write_disposable_only():
    """Require an explicitly disposable test DB, not just an env flag."""
    if getattr(settings, "SAEIT_ENV", None) != "ci":
        return False
    db = connection.settings_dict
    if db.get("ENGINE") != "django.db.backends.sqlite3":
        return False
    name = str(db.get("NAME") or "")
    if name == ":memory:" or name.startswith("file:memorydb_"):
        return True
    path = Path(name)
    if not path.is_absolute():
        return False
    if path.name == "factory-0048-copy.sqlite3":
        return path.parent.name.startswith(".astra-0049-copy-")
    # GitHub Actions may generate ephemeral, non-sensitive CI SQLite.
    return path.name.startswith("astra-0049-") and path.suffix == ".sqlite3"


def _candidate(pid, source_count, evidence_count):
    item = {
        "legacy_factory_product_id": int(pid),
        "source_reference_count_unverified": int(source_count),
        "linked_evidence_row_count_unverified": int(evidence_count),
        "research_only": True,
        "market_demand_independently_verified": False,
        "retail_qualified": False,
        "claim": "Original legacy draft requires independent market and quality review",
    }
    digest = hashlib.sha256(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"legacy-factory-product:{pid}", digest, item


def _read(limit, after_id):
    with connection.cursor() as cursor:
        cursor.execute(QUERY, [after_id, limit])
        return cursor.fetchall()


class Command(BaseCommand):
    help = "Read-only by default: research-work intake from original unpublished factory drafts"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--apply-private", action="store_true")

    def handle(self, *args, **opts):
        limit, after_id = opts["limit"], opts["after_id"]
        apply = opts["apply_private"]
        if not (1 <= limit <= MAX_TICK) or after_id < 0:
            raise CommandError("Invalid bounded research intake window")
        if apply and not _can_write_disposable_only():
            raise CommandError("WRITE_BLOCKED: only disposable CI SQLite permitted")
        rows = _read(limit, after_id)
        counts = {"scanned": len(rows), "new_research_tasks": 0,
                  "updated_research_tasks": 0, "unchanged_research_tasks": 0}
        if apply:
            with transaction.atomic():
                for pid, sources, evidence in rows:
                    key, digest, item = _candidate(pid, sources, evidence)
                    existing = FactoryQueueItem.objects.select_for_update().filter(key=key).first()
                    if existing is None:
                        FactoryQueueItem.objects.create(
                            key=key, kind="discovery", stage="WAITING_FOR_EVIDENCE",
                            payload_digest=digest, record=item,
                            market_demand_verified=False, publication_allowed=False,
                            commercial_quality_score=None,
                        )
                        counts["new_research_tasks"] += 1
                    elif (existing.payload_digest == digest and
                          existing.stage == "WAITING_FOR_EVIDENCE" and
                          existing.market_demand_verified is False and
                          existing.publication_allowed is False and
                          existing.commercial_quality_score is None):
                        counts["unchanged_research_tasks"] += 1
                    else:
                        # Do not override an item that was reviewed or edited; it
                        # could contain useful human notes. No automatic resets.
                        counts["unchanged_research_tasks"] += 1
        counts.update({
            "mode": "DISPOSABLE_PRIVATE_WRITE" if apply else "READ_ONLY_PREVIEW",
            "last_product_id": int(rows[-1][0]) if rows else after_id,
            "customer_orders_needed": False, "network_calls": 0,
            "commercially_qualified_products": 0, "new_products_for_sale": 0,
            "stage45_auto_publishing": False, "payment_activated": False,
        })
        self.stdout.write(json.dumps(counts, sort_keys=True))

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List

from django.utils import timezone

from .models import AgentTask
from .task_runtime import TaskRuntime


@dataclass
class RecoverySummary:
    scanned: int = 0
    recovered: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class RecoveryScheduler:
    """Bounded stale-task recovery pass.

    TaskRuntime owns the actual state transition and retry policy. This service
    selects only tasks that are old enough to be candidates, then re-validates
    staleness under a row lock inside TaskRuntime.
    """

    def __init__(self, runtime=None):
        self.runtime = runtime or TaskRuntime()

    def recover(self, limit=50, stale_after_seconds=900):
        self._validate_limit(limit)
        self._validate_stale_after(stale_after_seconds)

        cutoff = timezone.now() - timedelta(seconds=stale_after_seconds)
        task_ids = list(
            AgentTask.objects.filter(
                status="running", updated_at__lte=cutoff
            )
            .order_by("updated_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        summary = RecoverySummary(scanned=len(task_ids))

        for task_id in task_ids:
            try:
                task = self.runtime.recover_stale(
                    task_id, stale_after_seconds=stale_after_seconds
                )
            except Exception as exc:
                summary.skipped += 1
                summary.errors.append(f"{task_id}: {exc}")
                continue

            if task.status == "queued":
                summary.recovered += 1
            elif task.status == "failed":
                summary.failed += 1
            else:
                summary.skipped += 1

        return summary

    @staticmethod
    def _validate_limit(limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")

    @staticmethod
    def _validate_stale_after(value):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("stale_after_seconds must be a positive integer")

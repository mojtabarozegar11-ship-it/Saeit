from dataclasses import dataclass, field
from typing import List

from .models import AgentTask
from .task_runtime import TaskExecutionError, TaskRuntime


@dataclass
class DispatchSummary:
    scanned: int = 0
    completed: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class QueueDispatcher:
    """Deterministic bounded dispatcher for the controlled task queue.

    TaskRuntime.claim() remains the authority for locking, identity,
    approval, risk, and retry policy.
    """

    def __init__(self, worker_runner, runtime=None):
        if worker_runner is None:
            raise ValueError("worker_runner is required")
        self.runtime = runtime or getattr(worker_runner, "runtime", None) or TaskRuntime()
        self.worker_runner = worker_runner

    def dispatch(self, limit=10):
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit <= 0:
            raise ValueError("limit must be positive")

        task_ids = list(
            AgentTask.objects.filter(status="queued")
            .order_by("created_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        summary = DispatchSummary(scanned=len(task_ids))

        for task_id in task_ids:
            try:
                task = self.worker_runner.run(task_id)
            except TaskExecutionError as exc:
                summary.skipped += 1
                summary.errors.append(f"{task_id}: {exc}")
                continue
            except Exception as exc:
                current = AgentTask.objects.filter(pk=task_id).only("status").first()
                status = getattr(current, "status", None)
                if status == "failed":
                    summary.failed += 1
                elif status == "queued":
                    summary.retried += 1
                else:
                    summary.skipped += 1
                summary.errors.append(f"{task_id}: {exc}")
                continue

            if task.status == "completed":
                summary.completed += 1
            elif task.status == "failed":
                summary.failed += 1
            elif task.status == "queued":
                summary.retried += 1
            else:
                summary.skipped += 1

        return summary

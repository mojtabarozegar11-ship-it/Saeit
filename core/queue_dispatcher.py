from dataclasses import dataclass, field
from typing import List

from .models import AgentTask
from .task_runtime import TaskExecutionError, TaskRuntime
from .worker_runner import WorkerRunner


@dataclass
class DispatchSummary:
    scanned: int = 0
    completed: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class QueueDispatcher:
    """Small, deterministic dispatcher for the controlled task queue.

    Concurrency safety is delegated to TaskRuntime.claim(), which locks and
    re-validates each task before execution.
    """

    def __init__(self, worker_runner, runtime=None):
        if worker_runner is None:
            raise ValueError("worker_runner is required")
        self.runtime = runtime or TaskRuntime()
        self.worker_runner = worker_runner

    def dispatch(self, limit=10):
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc
        if limit <= 0:
            raise ValueError("limit must be positive")

        summary = DispatchSummary()
        task_ids = list(
            AgentTask.objects.filter(status="queued")
            .order_by("id")
            .values_list("id", flat=True)[:limit]
        )
        summary.scanned = len(task_ids)

        for task_id in task_ids:
            try:
                task = self.worker_runner.run(task_id)
            except TaskExecutionError as exc:
                summary.skipped += 1
                summary.errors.append(f"{task_id}: {exc}")
                continue
            except Exception as exc:
                current = AgentTask.objects.get(pk=task_id)
                if current.status == "completed":
                    summary.completed += 1
                elif current.status == "failed":
                    summary.failed += 1
                elif current.status == "queued":
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

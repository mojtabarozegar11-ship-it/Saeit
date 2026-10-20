from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class CycleStats:
    internal_runs: int
    external_runs: int
    internal_failures: int
    external_failures: int
    running: bool

class AwakeningCycles:
    """Opt-in dual wake loop.

    Internal cycle (default 60s) performs bounded housekeeping/planning callbacks.
    External cycle (default 180s) performs one bounded work callback.
    Existing agent code is never patched or replaced. Overlap is prevented per loop.
    """
    def __init__(self, internal: Callable[[], Any], external: Callable[[], Any],
                 internal_seconds: float = 60.0, external_seconds: float = 180.0,
                 run_immediately: bool = False):
        if internal_seconds <= 0 or external_seconds <= 0:
            raise ValueError("cycle intervals must be positive")
        self.internal = internal
        self.external = external
        self.internal_seconds = float(internal_seconds)
        self.external_seconds = float(external_seconds)
        self.run_immediately = bool(run_immediately)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._internal_lock = threading.Lock()
        self._external_lock = threading.Lock()
        self._mu = threading.Lock()
        self._counts = {"internal_runs": 0, "external_runs": 0,
                        "internal_failures": 0, "external_failures": 0}

    def _record(self, key: str) -> None:
        with self._mu:
            self._counts[key] += 1

    def _invoke(self, kind: str, fn: Callable[[], Any], lock: threading.Lock) -> None:
        if not lock.acquire(blocking=False):
            return
        try:
            try:
                fn()
                self._record(f"{kind}_runs")
            except Exception:
                self._record(f"{kind}_failures")
                log.exception("%s awakening cycle failed", kind)
        finally:
            lock.release()

    def _loop(self, kind: str, fn: Callable[[], Any], interval: float, lock: threading.Lock) -> None:
        if self.run_immediately:
            self._invoke(kind, fn, lock)
        while not self._stop.wait(interval):
            self._invoke(kind, fn, lock)

    def start(self) -> "AwakeningCycles":
        if self.running:
            return self
        self._stop.clear()
        specs = (("internal", self.internal, self.internal_seconds, self._internal_lock),
                 ("external", self.external, self.external_seconds, self._external_lock))
        self._threads = [threading.Thread(target=self._loop, args=s, daemon=True,
                                          name=f"master-{s[0]}-awakening") for s in specs]
        for t in self._threads:
            t.start()
        return self

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads = []

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads) and not self._stop.is_set()

    def stats(self) -> CycleStats:
        with self._mu:
            c = dict(self._counts)
        return CycleStats(**c, running=self.running)

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()

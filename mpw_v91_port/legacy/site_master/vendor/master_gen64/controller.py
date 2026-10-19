from __future__ import annotations
from typing import Any, Callable
from master_gen56 import Generation56Controller
from .cycles import AwakeningCycles

class Generation64Controller:
    """Gen57-64 additive facade: preserves Gen56 and adds opt-in autonomous wake cycles."""
    def __init__(self, **gen56_kwargs):
        self.base = Generation56Controller(**gen56_kwargs)
        self._cycles = None

    def run(self, *args, **kwargs):
        return self.base.run(*args, **kwargs)

    def awaken(self, internal: Callable[[], Any], external: Callable[[], Any],
               internal_seconds: float = 60.0, external_seconds: float = 180.0,
               run_immediately: bool = False) -> AwakeningCycles:
        if self._cycles and self._cycles.running:
            return self._cycles
        self._cycles = AwakeningCycles(internal, external, internal_seconds,
                                       external_seconds, run_immediately).start()
        return self._cycles

    def sleep(self) -> None:
        if self._cycles:
            self._cycles.stop()

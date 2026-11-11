"""Provider-neutral robotics boundary: observation is portable, action is simulation-only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import RLock
from typing import Callable, Literal, Protocol


class EmbodimentError(RuntimeError):
    """Robot state or a requested command failed a boundary check."""


@dataclass(frozen=True)
class RobotState:
    robot_id: str
    observed_at: datetime
    connected: bool
    emergency_stop: bool
    battery_percent: int
    capabilities: frozenset[str]


class RobotAdapter(Protocol):
    """Read-only interface to a future vendor-specific device."""

    def observe(self) -> RobotState: ...


@dataclass(frozen=True)
class BodyCommand:
    request_id: str
    robot_id: str
    kind: Literal["say", "step"]
    text: str = ""
    distance_m: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id is required")
        if not isinstance(self.robot_id, str) or not self.robot_id.strip():
            raise ValueError("robot_id is required")
        if self.kind not in ("say", "step"):
            raise ValueError("unsupported command kind")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if type(self.distance_m) not in (int, float) or not isfinite(self.distance_m):
            raise ValueError("distance_m must be a finite number")
        if self.kind == "say":
            if not self.text.strip() or len(self.text) > 300 or self.distance_m != 0:
                raise ValueError("say requires 1-300 characters and no movement")
        elif self.text or not 0 < self.distance_m <= 0.25:
            raise ValueError("step requires 0 < distance_m <= 0.25 and no speech")


@dataclass(frozen=True)
class SimulationReceipt:
    request_id: str
    robot_id: str
    kind: str
    simulated: bool
    detail: str


class SimulatedBody:
    """An in-memory body with no network, microphone, or physical actuator."""

    def __init__(self, *, robot_id: str = "ava-sim", battery_percent: int = 100) -> None:
        if not isinstance(robot_id, str) or not robot_id.strip():
            raise ValueError("robot_id is required")
        if type(battery_percent) is not int or not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be 0..100")
        self.robot_id = robot_id
        self.battery_percent = battery_percent
        self.connected = True
        self.emergency_stop = False
        self.travelled_m = 0.0
        self.last_speech = ""

    def observe(self) -> RobotState:
        return RobotState(self.robot_id, datetime.now(timezone.utc), self.connected,
                          self.emergency_stop, self.battery_percent, frozenset({"say", "step"}))

    def _apply(self, command: BodyCommand) -> SimulationReceipt:
        if command.kind == "say":
            self.last_speech = command.text
            detail = "speech stored in simulator only"
        else:
            self.travelled_m += command.distance_m
            detail = f"simulated forward movement of {command.distance_m:.3f}m"
        return SimulationReceipt(command.request_id, self.robot_id, command.kind, True, detail)


class EmbodimentGateway:
    """Read any robot state; permit commands to *exactly* SimulatedBody only.

    A host-authenticated owner and independent authorizer are required. Model
    output alone never grants authorization. Real motors need a separate design.
    """

    def __init__(self, *, owner_id: str, body: RobotAdapter,
                 authorize: Callable[[str, BodyCommand], bool] | None = None) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required")
        if not callable(getattr(body, "observe", None)):
            raise TypeError("body must implement observe()")
        if authorize is not None and not callable(authorize):
            raise TypeError("authorize must be callable")
        self.owner_id = owner_id
        self._body = body
        self._authorize = authorize
        self._completed: set[str] = set()
        self._lock = RLock()

    def observe(self) -> RobotState:
        state = self._body.observe()
        if not isinstance(state, RobotState) or not isinstance(state.robot_id, str) or not state.robot_id.strip():
            raise EmbodimentError("invalid robot state or identity")
        if not isinstance(state.observed_at, datetime) or state.observed_at.tzinfo is None:
            raise EmbodimentError("timestamp must be timezone-aware")
        if type(state.connected) is not bool or type(state.emergency_stop) is not bool:
            raise EmbodimentError("invalid safety flags")
        if type(state.battery_percent) is not int or not 0 <= state.battery_percent <= 100:
            raise EmbodimentError("invalid battery value")
        if not isinstance(state.capabilities, frozenset) or any(not isinstance(v, str) for v in state.capabilities):
            raise EmbodimentError("invalid capabilities")
        return state

    def simulate(self, command: BodyCommand) -> SimulationReceipt:
        if not isinstance(command, BodyCommand):
            raise TypeError("command must be BodyCommand")
        with self._lock:
            if type(self._body) is not SimulatedBody:  # no subclass or hardware driver
                raise EmbodimentError("physical actuation is unavailable")
            if command.request_id in self._completed:
                raise EmbodimentError("replayed command")
            state = self.observe()
            if command.robot_id != state.robot_id:
                raise EmbodimentError("command targets another robot")
            now = datetime.now(timezone.utc)
            if not now - timedelta(seconds=5) <= state.observed_at <= now:
                raise EmbodimentError("stale or future-dated observation")
            if not state.connected or state.emergency_stop:
                raise EmbodimentError("body unavailable or emergency-stopped")
            if command.kind not in state.capabilities:
                raise EmbodimentError("capability is unavailable")
            if command.kind == "step" and state.battery_percent < 20:
                raise EmbodimentError("battery below safe movement threshold")
            if self._authorize is None or self._authorize(self.owner_id, command) is not True:
                raise PermissionError("independent host authorization required")
            receipt = self._body._apply(command)
            self._completed.add(command.request_id)
            return receipt

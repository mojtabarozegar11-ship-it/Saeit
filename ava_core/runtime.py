"""Single composition root for AVA's memory, reasoning, goals and embodiment.

All capabilities share one authenticated owner and lifecycle. Nothing here
automatically invokes external tools, performs trades, or actuates real robots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .affect import AffectSnapshot, AffectiveCompanion, PersonalityTraits
from .core import Ava, AvaReply, Brain, MemoryItem, MemoryStore
from .embodiment import BodyCommand, EmbodimentGateway, RobotAdapter, RobotState, SimulatedBody, SimulationReceipt
from .goals import AutonomousGoalDirector, GoalDecision, GoalOutcome, GoalProposer


@dataclass(frozen=True)
class AvaTurn:
    """One audited logical turn with conversation and mood-style snapshot."""

    owner_id: str
    reply: AvaReply
    affect: AffectSnapshot


@dataclass(frozen=True)
class AvaRuntimeStatus:
    owner_id: str
    memory_items: int
    goal_outcomes: int
    romantic_mode: bool
    body: RobotState
    brain_model_verified: bool = False
    physical_actuation_enabled: bool = False


class AvaRuntime:
    """One owner-scoped runtime; collaborators are injected, never discovered.

    The host authenticates owner_id and configures model/provider, memory,
    approvals and (future) read-only robot interface. In particular a goal
    decision cannot directly authorize a robot or any other external action.
    """

    def __init__(
        self,
        *,
        owner_id: str,
        brain: Brain,
        propose_goals: GoalProposer,
        memory: MemoryStore | None = None,
        traits: PersonalityTraits | None = None,
        authorize_romantic_session: Callable[[str], bool] | None = None,
        body: RobotAdapter | None = None,
        authorize_simulation: Callable[[str, BodyCommand], bool] | None = None,
    ) -> None:
        self.affect = AffectiveCompanion(
            owner_id=owner_id, traits=traits,
            authorize_romantic_session=authorize_romantic_session,
        )
        self.assistant = Ava(
            owner_id=owner_id, brain=brain, memory=memory,
            style_guidance=self.affect.style_guidance,
        )
        self.goals = AutonomousGoalDirector(owner_id=owner_id, proposer=propose_goals)
        self.body = EmbodimentGateway(
            owner_id=owner_id, body=body if body is not None else SimulatedBody(),
            authorize=authorize_simulation,
        )
        self.owner_id = owner_id

    def converse(self, message: str, *, affect_signal: str | None = None,
                 use_memories: bool = False) -> AvaTurn:
        """One input -> optional affect update -> trusted guidance -> brain."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must not be blank")
        if affect_signal is not None:
            if not isinstance(affect_signal, str) or affect_signal not in self.affect.SIGNALS:
                raise ValueError("unknown affect signal")
            self.affect.notice(affect_signal)
        reply = self.assistant.converse(message, use_memories=use_memories)
        return AvaTurn(self.owner_id, reply, self.affect.snapshot())

    def remember(self, text: str, *, consent: bool = False) -> MemoryItem:
        return self.assistant.remember(text, consent=consent)

    def forget(self, memory_id: str) -> bool:
        return self.assistant.forget(memory_id)

    def choose_goal(self) -> GoalDecision:
        return self.goals.decide()

    def record_goal(self, goal_id: str, *, completed: bool, evidence: str) -> GoalOutcome:
        return self.goals.record_outcome(goal_id, completed=completed, evidence=evidence)

    def set_romantic_mode(self, enabled: bool) -> AffectSnapshot:
        return self.affect.set_romantic_mode(enabled)

    def observe_body(self) -> RobotState:
        return self.body.observe()

    def simulate_body_command(self, command: BodyCommand) -> SimulationReceipt:
        return self.body.simulate(command)

    def status(self) -> AvaRuntimeStatus:
        return AvaRuntimeStatus(
            owner_id=self.owner_id,
            memory_items=len(self.assistant.list_memories()),
            goal_outcomes=len(self.goals.history()),
            romantic_mode=self.affect.snapshot().romantic_mode,
            body=self.body.observe(),
        )

"""Single composition root for AVA's memory, reasoning, goals and embodiment.

All capabilities share one authenticated owner and lifecycle. Nothing here
automatically invokes external tools, performs trades, or actuates real robots.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Mapping

from .affect import AffectSnapshot, AffectiveCompanion, PersonalityTraits
from .audit import SQLiteCodeAuditTrail
from .core import Ava, AvaReply, Brain, MemoryItem, MemoryStore
from .embodiment import BodyCommand, EmbodimentGateway, RobotAdapter, RobotState, SimulatedBody, SimulationReceipt
from .evolution import ApprovedCodeBundle, CheckEvidence, CodeEvolutionDirector, CodeProposal, CodeProposer, CodeReview, CodeRollbackPlan
from .goals import AutonomousGoalDirector, GoalDecision, GoalOutcome, GoalProposer
from .sandbox import IsolatedReviewRunner, SandboxResult


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
    code_reviews: int = 0
    isolated_review_runner_configured: bool = False
    code_audit_enabled: bool = False
    code_audit_events: int = 0


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
        code_proposer: CodeProposer | None = None,
        review_runner: IsolatedReviewRunner | None = None,
        code_audit: SQLiteCodeAuditTrail | None = None,
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
        self.evolution = CodeEvolutionDirector(owner_id=owner_id, proposer=code_proposer)
        if review_runner is not None and review_runner.owner_id != owner_id:
            raise PermissionError("Isolated review runner owner mismatch")
        self.review_runner = review_runner
        self.code_audit = code_audit
        self._verified_checks: dict[str, CheckEvidence] = {}
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

    def propose_code_change(self, goal: str, *, trusted_files: Mapping[str, str]) -> CodeReview:
        """Generate and syntax-review a change; never execute or install it."""
        review = self.evolution.propose(goal, trusted_files=trusted_files)
        self._audit_review(review)
        return review

    def review_code_change(self, proposal: CodeProposal, *, trusted_files: Mapping[str, str]) -> CodeReview:
        review = self.evolution.stage(proposal, trusted_files=trusted_files)
        self._audit_review(review)
        return review

    def _audit(self, kind: str, review_id: str, data_sha256: str) -> None:
        if self.code_audit is not None:
            self.code_audit.append(self.owner_id, review_id, kind, data_sha256)

    def _audit_review(self, review: CodeReview) -> None:
        if self.code_audit is not None:
            if not any(entry.kind == "review_staged" and entry.review_id == review.review_id
                       for entry in self.code_audit.history(self.owner_id)):
                self._audit("review_staged", review.review_id, review.review_id)

    @staticmethod
    def _evidence_digest(evidence: CheckEvidence) -> str:
        data = json.dumps({
            "review_id": evidence.review_id, "passed": evidence.passed,
            "isolated": evidence.isolated, "tests_run": evidence.tests_run,
            "runner": evidence.runner, "details": evidence.details,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode()).hexdigest()

    def evaluate_code_change(self, review_id: str, *, trusted_tree: Mapping[str, str]) -> SandboxResult:
        """Run approved local regression suite only through the isolated runner."""
        if self.review_runner is None:
            raise PermissionError("No isolated runner was configured")
        review = self.evolution.get_review(review_id)
        if review is None:
            raise ValueError("Unknown code review")
        self._verified_checks.pop(review_id, None)
        if self.code_audit is not None and not any(
            event.kind == "review_staged" and event.review_id == review_id
            for event in self.code_audit.history(self.owner_id)
        ):
            raise PermissionError("Cannot evaluate a review without a verified audit stage event")
        result = self.review_runner.evaluate(review, trusted_tree=trusted_tree)
        self._audit(
            "review_evaluated_pass" if result.evidence.passed else "review_evaluated_fail",
            review.review_id, self._evidence_digest(result.evidence),
        )
        if result.evidence.passed:
            self._verified_checks[review.review_id] = result.evidence
        else:
            self._verified_checks.pop(review.review_id, None)
        return result

    def approve_code_handoff(
        self, review_id: str, *, evidence: CheckEvidence,
        authorize: Callable[[str, CodeReview], bool] | None = None,
    ) -> ApprovedCodeBundle:
        if self._verified_checks.get(review_id) != evidence:
            raise PermissionError("Only evidence observed from this runtime's isolated runner is accepted")
        bundle = self.evolution.approve_handoff(review_id, evidence=evidence, authorize=authorize)
        self._audit("handoff_approved", review_id, self._evidence_digest(evidence))
        return bundle

    def prepare_code_rollback(
        self, review_id: str, *, trusted_before: Mapping[str, str],
        trusted_current: Mapping[str, str],
    ) -> CodeRollbackPlan:
        plan = self.evolution.prepare_rollback(
            review_id, trusted_before=trusted_before, trusted_current=trusted_current,
        )
        self._audit("rollback_prepared", review_id, plan.plan_sha256)
        return plan

    def status(self) -> AvaRuntimeStatus:
        return AvaRuntimeStatus(
            owner_id=self.owner_id,
            memory_items=len(self.assistant.list_memories()),
            goal_outcomes=len(self.goals.history()),
            romantic_mode=self.affect.snapshot().romantic_mode,
            body=self.body.observe(),
            code_reviews=self.evolution.review_count(),
            isolated_review_runner_configured=self.review_runner is not None,
            code_audit_enabled=self.code_audit is not None,
            code_audit_events=(self.code_audit.verify(self.owner_id).event_count
                               if self.code_audit is not None else 0),
        )

"""AVA: a private, provider-neutral conversational assistant core."""

from .core import Ava, AvaMemory, AvaReply, ConsentError, MemoryItem
from .affect import AffectSnapshot, AffectiveCompanion, PersonalityTraits
from .embodiment import BodyCommand, EmbodimentError, EmbodimentGateway, RobotAdapter, RobotState, SimulatedBody, SimulationReceipt
from .goals import AutonomousGoalDirector, GoalAssessment, GoalDecision, GoalOutcome, GoalProposal
from .runtime import AvaRuntime, AvaRuntimeStatus, AvaTurn
from .storage import EncryptedSQLiteMemory, MemoryIntegrityError, MemoryKeyError
from .evolution import (
    ApprovedCodeBundle, CheckEvidence, CodeEdit, CodeEvolutionDirector,
    CodeProposal, CodeProposalError, CodeReview, ReviewedFile,
)
from .sandbox import IsolatedReviewRunner, IsolationUnavailable, SandboxResult

__all__ = [
    "Ava", "AvaMemory", "AvaReply", "ConsentError", "MemoryItem",
    "AutonomousGoalDirector", "GoalAssessment", "GoalDecision", "GoalOutcome", "GoalProposal",
    "BodyCommand", "EmbodimentError", "EmbodimentGateway", "RobotAdapter", "RobotState",
    "SimulatedBody", "SimulationReceipt",
    "AffectSnapshot", "AffectiveCompanion", "PersonalityTraits",
    "AvaRuntime", "AvaRuntimeStatus", "AvaTurn",
    "EncryptedSQLiteMemory", "MemoryIntegrityError", "MemoryKeyError",
    "ApprovedCodeBundle", "CheckEvidence", "CodeEdit", "CodeEvolutionDirector",
    "CodeProposal", "CodeProposalError", "CodeReview", "ReviewedFile",
    "IsolatedReviewRunner", "IsolationUnavailable", "SandboxResult",
]

"""Internal components of the single mojtaba.bot.ai runtime."""

from .identity import BOT_ID

from .core import Ava, AvaMemory, AvaReply, ConsentError, ConversationEngine, MemoryItem
from .affect import AffectSnapshot, AffectiveCompanion, PersonalityTraits
from .embodiment import BodyCommand, EmbodimentError, EmbodimentGateway, RobotAdapter, RobotState, SimulatedBody, SimulationReceipt
from .goals import AutonomousGoalDirector, GoalAssessment, GoalDecision, GoalOutcome, GoalProposal
from .runtime import AvaRuntime, AvaRuntimeStatus, AvaTurn, MojtabaBot
from .capabilities import (
    ActionReceipt, ActionRequest, AdapterResult, CapabilityAdapter, CapabilityHub,
    CapabilitySpec, OperationSpec,
)
from .storage import EncryptedSQLiteMemory, MemoryIntegrityError, MemoryKeyError
from .evolution import (
    ApprovedCodeBundle, CheckEvidence, CodeEdit, CodeEvolutionDirector,
    CodeProposal, CodeProposalError, CodeReview, ReviewedFile, DevelopmentScope,
)
from .sandbox import IsolatedReviewRunner, IsolationUnavailable, SandboxResult
from .audit import AuditEvent, AuditIntegrityError, AuditKeyError, AuditVerification, SQLiteCodeAuditTrail
from .evolution import CodeRollbackPlan, RollbackFile

__all__ = [
    "BOT_ID",
    "Ava", "AvaMemory", "AvaReply", "ConsentError", "ConversationEngine", "MemoryItem",
    "MojtabaBot", "ActionReceipt", "ActionRequest", "AdapterResult",
    "CapabilityAdapter", "CapabilityHub", "CapabilitySpec", "OperationSpec",
    "AutonomousGoalDirector", "GoalAssessment", "GoalDecision", "GoalOutcome", "GoalProposal",
    "BodyCommand", "EmbodimentError", "EmbodimentGateway", "RobotAdapter", "RobotState",
    "SimulatedBody", "SimulationReceipt",
    "AffectSnapshot", "AffectiveCompanion", "PersonalityTraits",
    "AvaRuntime", "AvaRuntimeStatus", "AvaTurn",
    "EncryptedSQLiteMemory", "MemoryIntegrityError", "MemoryKeyError",
    "ApprovedCodeBundle", "CheckEvidence", "CodeEdit", "CodeEvolutionDirector",
    "CodeProposal", "CodeProposalError", "CodeReview", "ReviewedFile", "DevelopmentScope",
    "IsolatedReviewRunner", "IsolationUnavailable", "SandboxResult",
    "AuditEvent", "AuditIntegrityError", "AuditKeyError", "AuditVerification", "SQLiteCodeAuditTrail",
    "CodeRollbackPlan", "RollbackFile",
]

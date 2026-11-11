"""AVA: a private, provider-neutral conversational assistant core."""

from .core import Ava, AvaMemory, AvaReply, ConsentError, MemoryItem
from .embodiment import BodyCommand, EmbodimentError, EmbodimentGateway, RobotAdapter, RobotState, SimulatedBody, SimulationReceipt
from .goals import AutonomousGoalDirector, GoalAssessment, GoalDecision, GoalOutcome, GoalProposal

__all__ = [
    "Ava", "AvaMemory", "AvaReply", "ConsentError", "MemoryItem",
    "AutonomousGoalDirector", "GoalAssessment", "GoalDecision", "GoalOutcome", "GoalProposal",
    "BodyCommand", "EmbodimentError", "EmbodimentGateway", "RobotAdapter", "RobotState",
    "SimulatedBody", "SimulationReceipt",
]

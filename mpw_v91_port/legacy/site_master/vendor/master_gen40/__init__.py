"""Optional additive Master Agent generations 33-40. Gen32 and all legacy packages remain untouched."""
from .uncertainty import UncertaintyCalibrator, ConfidenceBand
from .diversity import DiversityPortfolio, DiverseSelection
from .journal import IdempotentJournal, JournalEntry
from .canary import ShadowCanaryGate, CanaryDecision
from .deadline import DeadlinePlanner, DeadlinePlan
from .replay import DeterministicReplayLedger
from .state import VersionedStateStore, StateSnapshot
from .controller import Generation40Controller, Generation40Run
from .proof import Generation40ProofGate, LegacyManifestVerifier, PreservationProof
__all__=['UncertaintyCalibrator','ConfidenceBand','DiversityPortfolio','DiverseSelection','IdempotentJournal','JournalEntry','ShadowCanaryGate','CanaryDecision','DeadlinePlanner','DeadlinePlan','DeterministicReplayLedger','VersionedStateStore','StateSnapshot','Generation40Controller','Generation40Run','Generation40ProofGate','LegacyManifestVerifier','PreservationProof']

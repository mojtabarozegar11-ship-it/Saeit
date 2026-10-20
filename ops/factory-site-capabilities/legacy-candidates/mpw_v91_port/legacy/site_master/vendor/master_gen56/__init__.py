"""Optional additive Master Agent generations 49-56. Every Gen48/legacy byte remains untouched."""
from .risk import RiskAwareSelector, RiskDecision
from .circuit import CircuitBreaker, CircuitState
from .hedge import HedgedExecutor, HedgeResult
from .cache import AdaptiveResultCache, CacheReport
from .drift import DriftDetector, DriftReport
from .learning import OutcomeLearner, OutcomeEstimate
from .slo import SLOGuard, SLODecision
from .controller import Generation56Controller, Generation56Run
from .proof import Generation56ProofGate, LegacyManifestVerifier, PreservationProof
__all__=['RiskAwareSelector','RiskDecision','CircuitBreaker','CircuitState','HedgedExecutor','HedgeResult','AdaptiveResultCache','CacheReport','DriftDetector','DriftReport','OutcomeLearner','OutcomeEstimate','SLOGuard','SLODecision','Generation56Controller','Generation56Run','Generation56ProofGate','LegacyManifestVerifier','PreservationProof']

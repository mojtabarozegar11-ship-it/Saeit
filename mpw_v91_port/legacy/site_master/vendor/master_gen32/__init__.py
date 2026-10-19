"""Optional additive Master Agent generations 29-32. Legacy packages remain untouched."""
from .adaptive import AdaptiveCapabilityRegistry, CapabilityStats
from .router import RiskAwareRouter, RouteDecision
from .resilience import DeterministicCircuitBreaker, CircuitState
from .controller import Generation32Controller, Generation32Run
from .proof import LegacyManifestVerifier, PreservationProof, Generation32ProofGate
__all__=['AdaptiveCapabilityRegistry','CapabilityStats','RiskAwareRouter','RouteDecision','DeterministicCircuitBreaker','CircuitState','Generation32Controller','Generation32Run','LegacyManifestVerifier','PreservationProof','Generation32ProofGate']

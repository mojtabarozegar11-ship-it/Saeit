from master_gen56 import Generation56ProofGate, LegacyManifestVerifier, PreservationProof

class Generation64ProofGate(Generation56ProofGate):
    """Gen64 keeps the Gen56 >=40% measured-evidence and preservation gates."""
    pass

__all__ = ["Generation64ProofGate", "LegacyManifestVerifier", "PreservationProof"]

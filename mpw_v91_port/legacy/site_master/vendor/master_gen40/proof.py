from master_gen32 import Generation32ProofGate, LegacyManifestVerifier, PreservationProof

class Generation40ProofGate(Generation32ProofGate):
    """Gen40 keeps the >=40% production evidence requirement and byte-preservation proof."""
    pass

__all__=['Generation40ProofGate','LegacyManifestVerifier','PreservationProof']
